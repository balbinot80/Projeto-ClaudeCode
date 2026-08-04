/**
 * Sync Jueri pedidos → Supabase pedidos_cache
 * Roda em: node scripts/sync-pedidos.mjs
 * Requer: JUERI_BASE_URL, JUERI_TOKEN, SUPABASE_URL, SUPABASE_KEY (anon ou service)
 */

import { createClient } from '@supabase/supabase-js'

const JUERI_BASE_URL = process.env.JUERI_BASE_URL
const JUERI_TOKEN    = process.env.JUERI_TOKEN
const SUPABASE_URL   = process.env.SUPABASE_URL   || process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY   = process.env.SUPABASE_KEY   || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!JUERI_BASE_URL || !JUERI_TOKEN || !SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Variáveis obrigatórias: JUERI_BASE_URL, JUERI_TOKEN, SUPABASE_URL, SUPABASE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

async function fetchPage(page, retries = 3) {
  const url = `${JUERI_BASE_URL}/pedido?page=${page}`
  for (let i = 0; i < retries; i++) {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${JUERI_TOKEN}`, Accept: 'application/json' },
    })
    if (res.status === 429) {
      console.log(`  Rate limit na página ${page}, aguardando 15s...`)
      await new Promise(r => setTimeout(r, 15000))
      continue
    }
    if (!res.ok) throw new Error(`Jueri retornou ${res.status} na página ${page}`)
    return await res.json()
  }
  throw new Error(`Falhou após ${retries} tentativas na página ${page}`)
}

function mapRow(p) {
  return {
    id:                      p.id,
    codigo_pedido:           p.codigo_pedido   ?? null,
    status:                  p.status          ?? null,
    fk_revendedor_id:        p.fk_revendedor_id ?? null,
    supervisor_nome:         p.supervisor_nome  ?? null,
    data_acerto:             p.data_acerto      ? p.data_acerto.slice(0, 10) : null,
    data_baixa:              p.data_baixa       ? p.data_baixa.slice(0, 10)  : null,
    data_criacao:            p.data_criacao     ? p.data_criacao.slice(0, 10): null,
    valor_total:             parseFloat(p.valor_total)             || 0,
    valor_pre_baixa:         parseFloat(p.valor_pre_baixa)         || 0,
    valor_total_antes_baixa: parseFloat(p.valor_total_antes_baixa) || 0,
    comprador_nome:          p.comprador?.nome  ?? null,
    synced_at:               new Date().toISOString(),
  }
}

async function upsertBatch(rows) {
  const { error } = await supabase
    .from('pedidos_cache')
    .upsert(rows, { onConflict: 'id' })
  if (error) throw new Error(`Supabase upsert falhou: ${error.message}`)
}

async function main() {
  console.log('=== Sync Jueri → Supabase iniciado ===')
  const startedAt = Date.now()
  let page = 1
  let lastPage = 1
  let total = 0

  while (true) {
    process.stdout.write(`Página ${page}/${lastPage > 1 ? lastPage : '?'}... `)
    const json = await fetchPage(page)

    const rows = (json.data ?? []).map(mapRow)
    if (rows.length > 0) {
      await upsertBatch(rows)
      total += rows.length
    }

    lastPage = json.last_page ?? 1
    console.log(`${rows.length} registros`)

    if (!json.next_page_url) break
    page++
    await new Promise(r => setTimeout(r, 200)) // pausa gentil entre páginas
  }

  // Registra no log de sincronização
  await supabase.from('sync_log').insert({ tabela: 'pedidos_cache', total_rows: total })

  const elapsed = ((Date.now() - startedAt) / 1000).toFixed(1)
  console.log(`\n=== Concluído: ${total} pedidos em ${elapsed}s ===`)
}

main().catch(err => {
  console.error('ERRO:', err.message)
  process.exit(1)
})
