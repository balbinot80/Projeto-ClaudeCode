import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const BATCH = 1000

export async function GET() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const allRows: { status: string; data_baixa: string | null; data_acerto: string | null; data_criacao: string | null }[] = []
  let from = 0

  while (true) {
    const { data, error } = await supabase
      .from('pedidos_cache')
      .select('status,data_baixa,data_acerto,data_criacao')
      .order('id')
      .range(from, from + BATCH - 1)

    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    if (!data || data.length === 0) break
    allRows.push(...data)
    if (data.length < BATCH) break
    from += BATCH
  }

  if (allRows.length === 0) return NextResponse.json({ total: 0 })

  const byAnoMes: Record<string, { baixado: number; aberto: number }> = {}
  let semDataBaixa = 0, semDataAcerto = 0

  for (const r of allRows) {
    if (!r.data_baixa) semDataBaixa++
    if (!r.data_acerto) semDataAcerto++

    const datRef = r.status === 'Baixado' ? r.data_baixa : r.data_acerto
    if (datRef) {
      const ym = datRef.slice(0, 7)
      if (!byAnoMes[ym]) byAnoMes[ym] = { baixado: 0, aberto: 0 }
      if (r.status === 'Baixado') byAnoMes[ym].baixado++
      else byAnoMes[ym].aberto++
    }
  }

  const statusCount: Record<string, number> = {}
  for (const r of allRows) statusCount[r.status] = (statusCount[r.status] || 0) + 1

  return NextResponse.json({
    total: allRows.length,
    semDataBaixa,
    semDataAcerto,
    statusCount,
    porMes: Object.fromEntries(Object.entries(byAnoMes).sort()),
    amostra: allRows.slice(0, 3),
  })
}
