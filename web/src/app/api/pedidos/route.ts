import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const COLS = 'id,codigo_pedido,status,fk_revendedor_id,supervisor_nome,data_acerto,data_baixa,data_criacao,valor_total,valor_pre_baixa,valor_total_antes_baixa,comprador_nome,synced_at'
const BATCH = 1000

export async function GET() {
  const supabase = await createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  // Busca todos os pedidos paginando em lotes de 1000 (Supabase limita 1000/chamada)
  const allRows: Record<string, unknown>[] = []
  let from = 0

  while (true) {
    const { data: batch, error } = await supabase
      .from('pedidos_cache')
      .select(COLS)
      .order('id')
      .range(from, from + BATCH - 1)

    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    if (!batch || batch.length === 0) break
    allRows.push(...batch)
    if (batch.length < BATCH) break
    from += BATCH
  }

  if (allRows.length === 0) {
    return NextResponse.json({ error: 'cache_empty' }, { status: 503 })
  }

  const pedidos = allRows.map(r => ({
    id:                      r.id,
    codigo_pedido:           r.codigo_pedido,
    status:                  r.status,
    fk_revendedor_id:        r.fk_revendedor_id,
    supervisor_nome:         r.supervisor_nome,
    data_acerto:             r.data_acerto,
    data_baixa:              r.data_baixa,
    data_criacao:            r.data_criacao,
    valor_total:             r.valor_total,
    valor_pre_baixa:         r.valor_pre_baixa,
    valor_total_antes_baixa: r.valor_total_antes_baixa,
    comprador:               r.comprador_nome ? { nome: r.comprador_nome } : null,
  }))

  const { data: logRow } = await supabase
    .from('sync_log')
    .select('synced_at')
    .eq('tabela', 'pedidos_cache')
    .order('synced_at', { ascending: false })
    .limit(1)
    .single()

  return NextResponse.json({
    pedidos,
    synced_at: logRow?.synced_at ?? null,
  })
}
