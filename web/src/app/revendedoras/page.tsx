'use client'

import { useEffect, useState, useMemo } from 'react'
import Nav from '@/components/Nav'
import { calcularMes, mesesDisponiveis, RevendedorasMetrics } from '@/lib/revendedoras'
import { Pedido } from '@/types/pedido'

function R(v: number) {
  return `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function KpiPrimary({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 11, letterSpacing: '0.06em', color: 'var(--au-text-muted)', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-cormorant, "Cormorant Garamond", Georgia, serif)', fontSize: 32, fontWeight: 600, lineHeight: 1.1, color: color || 'var(--au-text)' }}>
        {value}
      </span>
    </div>
  )
}

function KpiSub({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5" style={{ borderTop: '1px solid var(--au-border)' }}>
      <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 12, color: 'var(--au-text-muted)' }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-cormorant, "Cormorant Garamond", Georgia, serif)', fontSize: 18, fontWeight: 600, color: color || 'var(--au-text)' }}>
        {value}
      </span>
    </div>
  )
}

function MetricCard({ title, accent, children }: { title: string; accent?: string; children: React.ReactNode }) {
  return (
    <div
      className="rounded-2xl p-5 flex flex-col gap-4"
      style={{
        background: 'var(--au-surface)',
        border: '1px solid var(--au-border)',
        boxShadow: '0 2px 16px rgba(171,103,116,.07)',
      }}
    >
      <div className="flex items-center gap-2">
        <div className="w-1 h-4 rounded-full" style={{ background: accent || 'var(--au-primary)' }} />
        <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: accent || 'var(--au-primary)' }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  )
}

export default function RevendedorasPage() {
  const meses = useMemo(() => mesesDisponiveis(), [])
  const [mesSel, setMesSel] = useState(0)
  const [pedidos, setPedidos] = useState<Pedido[]>([])
  const [loading, setLoading] = useState(true)
  const [syncedAt, setSyncedAt] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'visao' | 'acertos' | 'alertas'>('visao')

  useEffect(() => {
    let cancelled = false

    async function fetchPedidos() {
      try {
        const res = await fetch('/api/pedidos')
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          if (body?.error === 'cache_empty') {
            setError('Dados ainda não sincronizados. Execute o sync manualmente ou aguarde o próximo ciclo automático.')
          } else {
            setError(`Erro ${res.status}: ${body?.error ?? res.statusText}`)
          }
          return
        }
        const json = await res.json()
        if (!cancelled) {
          setPedidos(json.pedidos ?? [])
          setSyncedAt(json.synced_at ?? null)
        }
      } catch (e) {
        if (!cancelled) setError(`Erro de rede: ${e}`)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchPedidos()
    return () => { cancelled = true }
  }, [])

  const { mes, ano, label: mesLabel } = meses[mesSel]
  const metrics: RevendedorasMetrics | null = useMemo(
    () => pedidos.length > 0 ? calcularMes(pedidos, mes, ano) : null,
    [pedidos, mes, ano]
  )

  const tabs = [
    { id: 'visao' as const,   label: 'Visão geral'  },
    { id: 'acertos' as const, label: 'Acertos do mês' },
    { id: 'alertas' as const, label: 'Alertas'       },
  ]

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--au-bg)' }}>
      <Nav />

      <main className="flex-1 p-6 flex flex-col gap-5 max-w-7xl mx-auto w-full">
        {/* Header + seletor de mês */}
        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-0.5">
            <h1
              style={{ fontFamily: 'var(--font-cormorant, "Cormorant Garamond", Georgia, serif)', fontSize: 26, fontWeight: 600, color: 'var(--au-primary)', letterSpacing: '-0.01em' }}
            >
              Vendas por supervisora
            </h1>
            {syncedAt && (
              <span style={{ fontSize: 11, color: 'var(--au-text-muted)', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
                Dados de {new Date(syncedAt).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
          <select
            value={mesSel}
            onChange={e => setMesSel(Number(e.target.value))}
            className="rounded-xl px-4 py-2 text-sm outline-none"
            style={{ border: '1px solid var(--au-border)', background: 'var(--au-surface)', color: 'var(--au-text)', fontFamily: 'var(--font-jost, Jost, sans-serif)', boxShadow: '0 1px 4px rgba(171,103,116,.08)' }}
          >
            {meses.map((m, i) => (
              <option key={i} value={i}>{m.label}</option>
            ))}
          </select>
        </div>

        {loading && (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
                 style={{ borderColor: 'var(--au-primary)', borderTopColor: 'transparent' }} />
            <p className="text-sm" style={{ color: 'var(--au-text-muted)' }}>Carregando…</p>
          </div>
        )}

        {error && (
          <div className="rounded-lg p-4" style={{ background: '#FEE2E2', color: '#B91C1C' }}>
            Erro ao carregar: {error}
          </div>
        )}

        {!loading && !error && metrics && (
          <>
            {/* Blocos de métricas */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCard title={`Acertos — ${mesLabel}`}>
                <KpiPrimary label="Previstos no mês" value={metrics.nAcertosMes} />
                <div className="flex flex-col">
                  <KpiSub label="Já baixados"       value={metrics.nAcertosBaixados} color="var(--au-primary)" />
                  <KpiSub label="Pendentes"          value={metrics.nAcertosPendentes} />
                  <KpiSub label="Postergados +30d"   value={metrics.nPostergados} color="var(--au-accent)" />
                  <KpiSub label="Abaixo do mínimo"   value={metrics.nAbaixoMin} color="var(--au-accent)" />
                  <KpiSub label="Zeradas"            value={metrics.nZeradas} color="#B91C1C" />
                </div>
              </MetricCard>

              <MetricCard title="Financeiro" accent="var(--au-accent)">
                <KpiPrimary label="Total vendido" value={R(metrics.totalLiquido)} color="var(--au-accent)" />
                <div className="flex flex-col">
                  <KpiSub label="Baixados"              value={R(metrics.totalBx)} />
                  <KpiSub label="Pré-baixa"             value={R(metrics.totalPb)} />
                  <KpiSub label="Ticket médio previsto"  value={R(metrics.ticketPrevisto)} color="var(--au-primary)" />
                  <KpiSub label="Ticket médio baixado"   value={R(metrics.ticketBaixado)} />
                </div>
              </MetricCard>

              <MetricCard title="Alertas" accent="#B91C1C">
                {metrics.rowsBxZero.length > 0
                  ? <KpiPrimary label="Baixados c/ zero vendas" value={metrics.rowsBxZero.length} color="#B91C1C" />
                  : (
                    <div style={{ textAlign: 'center', padding: '20px 0' }}>
                      <div style={{ fontSize: 28, opacity: .4 }}>✦</div>
                      <p style={{ fontFamily: 'var(--font-cormorant, "Cormorant Garamond", serif)', fontSize: 16, color: 'var(--au-text-muted)', marginTop: 8 }}>
                        Nenhum alerta crítico
                      </p>
                    </div>
                  )
                }
                {metrics.nPostergados > 0 && (
                  <KpiSub label="Postergados +30 dias" value={metrics.nPostergados} color="var(--au-accent)" />
                )}
              </MetricCard>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b" style={{ borderColor: 'var(--au-border)' }}>
              {tabs.map(t => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className="px-4 py-2 text-sm font-medium transition border-b-2 -mb-px"
                  style={{
                    color: tab === t.id ? 'var(--au-primary)' : 'var(--au-text-muted)',
                    borderColor: tab === t.id ? 'var(--au-primary)' : 'transparent',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab: Visão geral por supervisora */}
            {tab === 'visao' && (
              <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--au-border)' }}>
                <table className="w-full text-sm">
                  <thead style={{ background: 'var(--au-primary-pale)' }}>
                    <tr>
                      {['Supervisora','Revendedoras','Baixado','Pré-baixa','Total','Abaixo mín.','Zeradas'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold"
                            style={{ color: 'var(--au-primary)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.porSupervisora.map((s, i) => (
                      <tr key={s.supervisora}
                          style={{ background: i % 2 === 0 ? 'var(--au-surface)' : 'var(--au-bg)' }}>
                        <td className="px-4 py-2.5 font-medium" style={{ color: 'var(--au-text)' }}>{s.supervisora}</td>
                        <td className="px-4 py-2.5 text-center" style={{ color: 'var(--au-text-muted)' }}>{s.revendedoras}</td>
                        <td className="px-4 py-2.5" style={{ color: 'var(--au-text)' }}>{R(s.baixado)}</td>
                        <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{R(s.preBaixa)}</td>
                        <td className="px-4 py-2.5 font-semibold" style={{ color: 'var(--au-text)' }}>{R(s.total)}</td>
                        <td className="px-4 py-2.5 text-center" style={{ color: s.abaixoMin > 0 ? '#C4985A' : 'var(--au-text-muted)' }}>{s.abaixoMin}</td>
                        <td className="px-4 py-2.5 text-center" style={{ color: s.zeradas > 0 ? '#B91C1C' : 'var(--au-text-muted)' }}>{s.zeradas}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab: Acertos do mês */}
            {tab === 'acertos' && (
              <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--au-border)' }}>
                <table className="w-full text-sm">
                  <thead style={{ background: 'var(--au-primary-pale)' }}>
                    <tr>
                      {['Nome','Supervisora','Data','Status','Dias ciclo','Valor'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold"
                            style={{ color: 'var(--au-primary)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.rowsAcertosMes.map((r, i) => (
                      <tr key={i} style={{ background: i % 2 === 0 ? 'var(--au-surface)' : 'var(--au-bg)' }}>
                        <td className="px-4 py-2.5" style={{ color: 'var(--au-text)' }}>{r.nome}</td>
                        <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.supervisora}</td>
                        <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.data}</td>
                        <td className="px-4 py-2.5">
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                                style={{ background: r.status === 'Baixado' ? '#DCFCE7' : '#FEF9C3',
                                         color: r.status === 'Baixado' ? '#166534' : '#854D0E' }}>
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-center"
                            style={{ color: r.diasCiclo > 30 ? '#C4985A' : 'var(--au-text-muted)' }}>
                          {r.diasCiclo}d
                        </td>
                        <td className="px-4 py-2.5 font-medium" style={{ color: 'var(--au-text)' }}>{R(r.valor)}</td>
                      </tr>
                    ))}
                    {metrics.rowsAcertosMes.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-sm"
                              style={{ color: 'var(--au-text-muted)' }}>Nenhum acerto em {mesLabel}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab: Alertas */}
            {tab === 'alertas' && (
              <div className="flex flex-col gap-4">
                {/* Baixados com zero vendas */}
                <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--au-border)' }}>
                  <div className="px-4 py-3" style={{ background: '#FEE2E2' }}>
                    <span className="text-sm font-semibold" style={{ color: '#991B1B' }}>
                      🔴 Baixados com zero vendas — {metrics.rowsBxZero.length} pedido(s)
                    </span>
                  </div>
                  {metrics.rowsBxZero.length > 0 ? (
                    <table className="w-full text-sm">
                      <thead style={{ background: 'var(--au-primary-pale)' }}>
                        <tr>
                          {['Nome','Supervisora','Pedido','Valor maleta','Data baixa'].map(h => (
                            <th key={h} className="px-4 py-3 text-left text-xs font-semibold"
                                style={{ color: 'var(--au-primary)' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.rowsBxZero.map((r, i) => (
                          <tr key={i} style={{ background: i % 2 === 0 ? 'var(--au-surface)' : 'var(--au-bg)' }}>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text)' }}>{r.nome}</td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.supervisora}</td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.codigoPedido}</td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text)' }}>{R(r.valorMaleta)}</td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.dataBaixa}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="px-4 py-6 text-sm" style={{ color: 'var(--au-text-muted)' }}>
                      Nenhum pedido baixado com zero vendas em {mesLabel}.
                    </p>
                  )}
                </div>

                {/* Postergados */}
                {metrics.rowsPostergados.length > 0 && (
                  <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--au-border)' }}>
                    <div className="px-4 py-3" style={{ background: '#FEF9C3' }}>
                      <span className="text-sm font-semibold" style={{ color: '#854D0E' }}>
                        ⏰ Postergados (+30 dias) — {metrics.rowsPostergados.length}
                      </span>
                    </div>
                    <table className="w-full text-sm">
                      <thead style={{ background: 'var(--au-primary-pale)' }}>
                        <tr>
                          {['Nome','Supervisora','Status','Criação','Acerto prev.','Dias'].map(h => (
                            <th key={h} className="px-4 py-3 text-left text-xs font-semibold"
                                style={{ color: 'var(--au-primary)' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.rowsPostergados.map((r, i) => (
                          <tr key={i} style={{ background: i % 2 === 0 ? 'var(--au-surface)' : 'var(--au-bg)' }}>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text)' }}>{r.nome}</td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.supervisora}</td>
                            <td className="px-4 py-2.5">
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                                    style={{ background: r.status === 'Baixado' ? '#DCFCE7' : '#FEF9C3',
                                             color: r.status === 'Baixado' ? '#166534' : '#854D0E' }}>
                                {r.status}
                              </span>
                            </td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.criacao}</td>
                            <td className="px-4 py-2.5" style={{ color: 'var(--au-text-muted)' }}>{r.acertoPrev}</td>
                            <td className="px-4 py-2.5 font-semibold" style={{ color: '#C4985A' }}>{r.dias}d</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
