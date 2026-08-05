import { Pedido } from '@/types/pedido'

export const MINIMO_REV = 300

export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null
  try {
    const d = new Date(s.slice(0, 10))
    return isNaN(d.getTime()) ? null : d
  } catch { return null }
}

function fmtDate(d: Date): string {
  return d.toLocaleDateString('pt-BR')
}

function n(v: number | string | null | undefined): number {
  return parseFloat(String(v || 0)) || 0
}

export interface AcertoRow {
  nome: string
  supervisora: string
  data: string
  status: string
  diasCiclo: number
  valor: number
}

export interface PostergadoRow {
  nome: string
  supervisora: string
  status: string
  criacao: string
  acertoPrev: string
  dias: number
}

export interface BxZeroRow {
  nome: string
  supervisora: string
  codigoPedido: string
  valorMaleta: number
  dataBaixa: string
}

export interface SupervisoraRow {
  supervisora: string
  revendedoras: number
  baixado: number
  preBaixa: number
  total: number
  abaixoMin: number
  zeradas: number
}

export interface RevendedorasMetrics {
  nAcertosMes: number
  nPostergados: number
  nAcertosBaixados: number
  nAcertosPendentes: number
  nAbaixoMin: number
  nZeradas: number
  totalBx: number
  totalPb: number
  totalLiquido: number
  ticketPrevisto: number
  ticketBaixado: number
  rowsAcertosMes: AcertoRow[]
  rowsPostergados: PostergadoRow[]
  rowsBxZero: BxZeroRow[]
  porSupervisora: SupervisoraRow[]
}

export function calcularMes(pedidos: Pedido[], mes: number, ano: number): RevendedorasMetrics {
  const rowsAcertosMes: AcertoRow[]    = []
  const rowsPostergados: PostergadoRow[] = []
  const rowsBxZero: BxZeroRow[]         = []

  // Mapa para resumo por supervisora
  const supMap: Record<string, {
    revIds: Set<number>; baixado: number; preBaixa: number;
    abaixoMin: Set<number>; zeradas: Set<number>
  }> = {}

  const revTotais: Record<number, number> = {}

  for (const p of pedidos) {
    const rid  = p.fk_revendedor_id
    const sup  = p.supervisor_nome || 'Sem supervisora'
    const nome = p.comprador?.nome || `Rev ${rid}`
    const status = p.status

    if (!supMap[sup]) {
      supMap[sup] = { revIds: new Set(), baixado: 0, preBaixa: 0, abaixoMin: new Set(), zeradas: new Set() }
    }

    const dAc = parseDate(p.data_acerto)
    const dBx = parseDate(p.data_baixa)
    const dCr = parseDate(p.data_criacao)

    // Acertos do mês (regra central de datas)
    if (status === 'Baixado' || status === 'Aberto') {
      const dMes = status === 'Baixado' ? dBx : dAc
      if (dMes && dMes.getMonth() + 1 === mes && dMes.getFullYear() === ano) {
        supMap[sup].revIds.add(rid) // só conta revendedoras com acerto no mês
        const val = status === 'Baixado' ? n(p.valor_total) : n(p.valor_pre_baixa)
        const diasCiclo = dCr ? Math.floor((dMes.getTime() - dCr.getTime()) / 86400000) : 0
        rowsAcertosMes.push({
          nome, supervisora: sup,
          data: fmtDate(dMes),
          status,
          diasCiclo,
          valor: val,
        })
        if (status === 'Baixado') {
          supMap[sup].baixado += val
          revTotais[rid] = (revTotais[rid] || 0) + val
        } else {
          supMap[sup].preBaixa += val
          revTotais[rid] = (revTotais[rid] || 0) + val
        }
        // Postergados (ciclo > 30 dias)
        if (dCr && diasCiclo > 30) {
          rowsPostergados.push({
            nome, supervisora: sup, status,
            criacao: fmtDate(dCr),
            acertoPrev: dAc ? fmtDate(dAc) : '—',
            dias: diasCiclo,
          })
        }
      }
    }

    // Baixados com zero vendas
    if (status === 'Baixado' && dBx &&
        dBx.getMonth() + 1 === mes && dBx.getFullYear() === ano &&
        n(p.valor_total) === 0) {
      rowsBxZero.push({
        nome, supervisora: sup,
        codigoPedido: p.codigo_pedido,
        valorMaleta: n(p.valor_total_antes_baixa),
        dataBaixa: fmtDate(dBx),
      })
    }
  }

  // Abaixo do mínimo e zeradas (baseado em totais do mês)
  for (const [sup, s] of Object.entries(supMap)) {
    for (const rid of s.revIds) {
      const t = revTotais[rid] || 0
      if (t === 0) s.zeradas.add(rid)
      else if (t < MINIMO_REV) s.abaixoMin.add(rid)
    }
  }

  const nAcertosBaixados = rowsAcertosMes.filter(r => r.status === 'Baixado').length
  const nAcertosPendentes = rowsAcertosMes.length - nAcertosBaixados
  const totalBx = rowsAcertosMes.filter(r => r.status === 'Baixado').reduce((s, r) => s + r.valor, 0)
  const totalPb = rowsAcertosMes.filter(r => r.status === 'Aberto').reduce((s, r) => s + r.valor, 0)

  const nAbaixoMin = Object.values(supMap).reduce((s, v) => s + v.abaixoMin.size, 0)
  const nZeradas   = Object.values(supMap).reduce((s, v) => s + v.zeradas.size, 0)

  const porSupervisora: SupervisoraRow[] = Object.entries(supMap).map(([sup, s]) => ({
    supervisora: sup,
    revendedoras: s.revIds.size,
    baixado: s.baixado,
    preBaixa: s.preBaixa,
    total: s.baixado + s.preBaixa,
    abaixoMin: s.abaixoMin.size,
    zeradas: s.zeradas.size,
  })).sort((a, b) => b.total - a.total)

  return {
    nAcertosMes: rowsAcertosMes.length,
    nPostergados: rowsPostergados.length,
    nAcertosBaixados,
    nAcertosPendentes,
    nAbaixoMin,
    nZeradas,
    totalBx,
    totalPb,
    totalLiquido: totalBx + totalPb,
    ticketPrevisto: rowsAcertosMes.length > 0 ? (totalBx + totalPb) / rowsAcertosMes.length : 0,
    ticketBaixado: nAcertosBaixados > 0 ? totalBx / nAcertosBaixados : 0,
    rowsAcertosMes,
    rowsPostergados,
    rowsBxZero,
    porSupervisora,
  }
}

export function mesesDisponiveis(n = 7, futuros = 1): { ano: number; mes: number; label: string }[] {
  const hoje = new Date()
  const result: { ano: number; mes: number; label: string }[] = []
  const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                 'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
  for (let i = -futuros; i < n - futuros; i++) {
    const d = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1)
    result.push({ ano: d.getFullYear(), mes: d.getMonth() + 1, label: `${MESES[d.getMonth()]} ${d.getFullYear()}` })
  }
  return result
}
