'use client'

import { useEffect, useState, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, TrendingUp, AlertTriangle, BarChart2, RefreshCw } from 'lucide-react'
import Nav from '@/components/Nav'
import { SkeletonCard } from '@/components/ui/skeleton'
import { Badge, statusVariant } from '@/components/ui/badge'
import { calcularMes, mesesDisponiveis, RevendedorasMetrics } from '@/lib/revendedoras'
import { Pedido } from '@/types/pedido'

/* ── Formatadores ─────────────────────────────────────────────────────── */
function R(v: number) {
  return `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/* ── Contador animado ─────────────────────────────────────────────────── */
function AnimatedNumber({ value, prefix = '', suffix = '', decimals = 0 }: {
  value: number; prefix?: string; suffix?: string; decimals?: number
}) {
  const [display, setDisplay] = useState(0)
  const prev = useRef(0)

  useEffect(() => {
    const start  = prev.current
    const end    = value
    const dur    = 700
    const t0     = performance.now()
    prev.current = value

    function step(now: number) {
      const p = Math.min(1, (now - t0) / dur)
      const eased = 1 - Math.pow(1 - p, 3)
      setDisplay(start + (end - start) * eased)
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [value])

  const formatted = decimals > 0
    ? display.toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    : Math.round(display).toLocaleString('pt-BR')

  return <>{prefix}{formatted}{suffix}</>
}

/* ── KPI Primary ──────────────────────────────────────────────────────── */
function KpiPrimary({ label, value, color, animate = true }: {
  label: string; value: number | string; color?: string; animate?: boolean
}) {
  const isNum = typeof value === 'number'
  const isR   = typeof value === 'string' && value.startsWith('R$')

  return (
    <div className="flex flex-col gap-1">
      <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 10, letterSpacing: '0.08em', color: 'var(--au-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 36, fontWeight: 600, lineHeight: 1, color: color || 'var(--au-text)' }}>
        {animate && isNum
          ? <AnimatedNumber value={value as number} />
          : animate && isR
          ? <>R$ <AnimatedNumber value={parseFloat(String(value).replace(/[^0-9,]/g, '').replace(',', '.'))} decimals={2} /></>
          : value}
      </span>
    </div>
  )
}

/* ── KPI Sub ──────────────────────────────────────────────────────────── */
function KpiSub({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex items-center justify-between py-2" style={{ borderTop: '1px solid var(--au-border)' }}>
      <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 12, color: 'var(--au-text-muted)' }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 19, fontWeight: 600, color: color || 'var(--au-text)' }}>
        {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
      </span>
    </div>
  )
}

/* ── Metric Card ──────────────────────────────────────────────────────── */
function MetricCard({ title, accent, icon: Icon, children }: {
  title: string; accent?: string; icon?: React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>;
  children: React.ReactNode
}) {
  return (
    <div
      className="rounded-2xl p-5 flex flex-col gap-4 h-full"
      style={{
        background:   'var(--au-surface)',
        border:       '1px solid var(--au-border)',
        boxShadow:    '0 1px 12px rgba(171,103,116,.06)',
      }}
    >
      <div className="flex items-center gap-2">
        <div className="w-0.5 h-4 rounded-full shrink-0" style={{ background: accent || 'var(--au-primary)' }} />
        {Icon && <Icon size={13} strokeWidth={2} color={accent || 'var(--au-primary)'} />}
        <span style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: accent || 'var(--au-primary)' }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  )
}

/* ── Select de mês ────────────────────────────────────────────────────── */
function MesSelect({ meses, value, onChange }: {
  meses: { label: string }[]
  value: number
  onChange: (i: number) => void
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="appearance-none pr-8 pl-4 py-2 text-sm rounded-xl outline-none cursor-pointer transition-all"
        style={{
          border:      '1px solid var(--au-border)',
          background:  'var(--au-surface)',
          color:       'var(--au-text)',
          fontFamily:  'var(--font-jost, Jost, sans-serif)',
          boxShadow:   '0 1px 4px rgba(171,103,116,.08)',
        }}
      >
        {meses.map((m, i) => <option key={i} value={i}>{m.label}</option>)}
      </select>
      <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                   style={{ color: 'var(--au-text-muted)' }} />
    </div>
  )
}

/* ── Tab Bar ──────────────────────────────────────────────────────────── */
const TABS = [
  { id: 'visao'   as const, label: 'Visão geral'   },
  { id: 'acertos' as const, label: 'Acertos do mês' },
  { id: 'alertas' as const, label: 'Alertas'        },
]

function TabBar({ active, onChange }: { active: string; onChange: (t: string) => void }) {
  return (
    <div className="flex gap-0 border-b relative" style={{ borderColor: 'var(--au-border)' }}>
      {TABS.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className="relative px-5 py-2.5 text-sm font-medium transition-colors duration-150"
          style={{
            color:      active === t.id ? 'var(--au-primary)' : 'var(--au-text-muted)',
            fontFamily: 'var(--font-jost, Jost, sans-serif)',
            letterSpacing: '0.02em',
          }}
        >
          {t.label}
          {active === t.id && (
            <motion.div
              layoutId="tab-indicator"
              className="absolute bottom-0 left-0 right-0 h-0.5"
              style={{ background: 'var(--au-primary)' }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}
        </button>
      ))}
    </div>
  )
}

/* ── Tabela base ──────────────────────────────────────────────────────── */
function AuTable({ headers, children, empty }: {
  headers: string[]; children: React.ReactNode; empty?: string
}) {
  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--au-border)' }}>
      <div style={{ overflowX: 'auto' }}>
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--au-primary-pale)' }}>
            <tr>
              {headers.map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold whitespace-nowrap"
                    style={{ color: 'var(--au-primary)', fontFamily: 'var(--font-jost, Jost, sans-serif)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
      {empty && (
        <div className="py-10 flex flex-col items-center gap-2" style={{ color: 'var(--au-text-muted)' }}>
          <span style={{ fontSize: 22, opacity: .35 }}>✦</span>
          <p style={{ fontFamily: 'var(--font-jost, Jost, sans-serif)', fontSize: 14, color: 'var(--au-text-muted)' }}>{empty}</p>
        </div>
      )}
    </div>
  )
}

function AuTr({ children, i }: { children: React.ReactNode; i: number }) {
  return (
    <tr
      className="transition-colors duration-100"
      style={{ background: i % 2 === 0 ? 'var(--au-surface)' : 'var(--au-bg)' }}
      onMouseEnter={e => (e.currentTarget.style.background = 'var(--au-primary-pale)')}
      onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? 'var(--au-surface)' : 'var(--au-bg)')}
    >
      {children}
    </tr>
  )
}

function Td({ children, muted, center }: { children: React.ReactNode; muted?: boolean; center?: boolean }) {
  return (
    <td className={`px-4 py-2.5 ${center ? 'text-center' : ''}`}
        style={{ color: muted ? 'var(--au-text-muted)' : 'var(--au-text)' }}>
      {children}
    </td>
  )
}

/* ══════════════════════════════════════════════════════════════════════ */
/*  Página principal                                                      */
/* ══════════════════════════════════════════════════════════════════════ */
export default function RevendedorasPage() {
  const meses  = useMemo(() => mesesDisponiveis(), [])
  const [mesSel, setMesSel] = useState(1) // índice 1 = mês atual (índice 0 é o futuro)
  const [pedidos,  setPedidos]  = useState<Pedido[]>([])
  const [loading,  setLoading]  = useState(true)
  const [syncedAt, setSyncedAt] = useState<string | null>(null)
  const [error,    setError]    = useState('')
  const [tab,      setTab]      = useState<'visao' | 'acertos' | 'alertas'>('visao')

  useEffect(() => {
    let cancelled = false

    async function fetchPedidos() {
      try {
        const res = await fetch('/api/pedidos')
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          if (!cancelled) setError(
            body?.error === 'cache_empty'
              ? 'Dados ainda não sincronizados. Execute o sync manualmente no GitHub Actions.'
              : `Erro ${res.status}: ${body?.error ?? res.statusText}`
          )
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

  const cardVariants = {
    hidden:  { opacity: 0, y: 16 },
    visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.35, ease: 'easeOut' as const } }),
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--au-bg)' }}>
      <Nav />

      <main className="flex-1 p-6 flex flex-col gap-5 max-w-7xl mx-auto w-full">

        {/* Header */}
        <div className="flex items-end justify-between">
          <div className="flex flex-col gap-0.5">
            <h1 className="font-display" style={{ fontSize: 22, fontWeight: 600, color: 'var(--au-primary)', letterSpacing: '-0.01em' }}>
              Vendas por supervisora
            </h1>
            {syncedAt && (
              <span className="flex items-center gap-1" style={{ fontSize: 11, color: 'var(--au-text-muted)', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
                <RefreshCw size={10} />
                Atualizado em {new Date(syncedAt).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
          <MesSelect meses={meses} value={mesSel} onChange={setMesSel} />
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[0, 1, 2].map(i => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* Erro */}
        {error && (
          <div className="rounded-xl p-4 flex items-center gap-3" style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#B91C1C' }}>
            <AlertTriangle size={16} />
            <span style={{ fontSize: 14 }}>{error}</span>
          </div>
        )}

        {/* Conteúdo */}
        {!loading && !error && metrics && (
          <>
            {/* Cards de KPI */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                <MetricCard key="acertos" title={`Acertos — ${mesLabel}`} icon={BarChart2}>
                  <KpiPrimary label="Previstos no mês" value={metrics.nAcertosMes} color="var(--au-primary)" />
                  <div className="flex flex-col">
                    <KpiSub label="Já baixados"      value={metrics.nAcertosBaixados}  color="var(--au-primary)" />
                    <KpiSub label="Pendentes"         value={metrics.nAcertosPendentes} />
                    <KpiSub label="Postergados +30d"  value={metrics.nPostergados}      color="#C4985A" />
                    <KpiSub label="Abaixo do mínimo"  value={metrics.nAbaixoMin}        color="#C4985A" />
                    <KpiSub label="Zeradas"           value={metrics.nZeradas}          color="#B91C1C" />
                  </div>
                </MetricCard>,

                <MetricCard key="financeiro" title="Financeiro" accent="#C4985A" icon={TrendingUp}>
                  <KpiPrimary label="Total vendido" value={R(metrics.totalLiquido)} color="#C4985A" animate={false} />
                  <div className="flex flex-col">
                    <KpiSub label="Baixados"               value={R(metrics.totalBx)}       color="var(--au-text)" />
                    <KpiSub label="Pré-baixa"              value={R(metrics.totalPb)}        />
                    <KpiSub label="Ticket médio previsto"  value={R(metrics.ticketPrevisto)} color="var(--au-primary)" />
                    <KpiSub label="Ticket médio baixado"   value={R(metrics.ticketBaixado)}  />
                  </div>
                </MetricCard>,

                <MetricCard key="alertas" title="Alertas" accent="#B91C1C" icon={AlertTriangle}>
                  {metrics.rowsBxZero.length > 0
                    ? <>
                        <KpiPrimary label="Baixados c/ zero vendas" value={metrics.rowsBxZero.length} color="#B91C1C" />
                        {metrics.nPostergados > 0 && <KpiSub label="Postergados +30d" value={metrics.nPostergados} color="#C4985A" />}
                      </>
                    : <div className="flex-1 flex flex-col items-center justify-center py-4 gap-2">
                        <span style={{ fontSize: 24, opacity: .3 }}>✦</span>
                        <p style={{ fontSize: 15, color: 'var(--au-text-muted)', textAlign: 'center', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
                          Nenhum alerta crítico
                        </p>
                      </div>
                  }
                </MetricCard>,
              ].map((card, i) => (
                <motion.div key={i} custom={i} initial="hidden" animate="visible" variants={cardVariants}>
                  {card}
                </motion.div>
              ))}
            </div>

            {/* Tabs */}
            <TabBar active={tab} onChange={t => setTab(t as typeof tab)} />

            {/* Conteúdo das tabs com fade */}
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
              >

                {/* ── Visão geral ── */}
                {tab === 'visao' && (
                  <AuTable
                    headers={['Supervisora', 'Revendedoras', 'Baixado', 'Pré-baixa', 'Total', 'Abaixo mín.', 'Zeradas']}
                    empty={metrics.porSupervisora.length === 0 ? `Nenhum acerto em ${mesLabel}` : undefined}
                  >
                    {metrics.porSupervisora.map((s, i) => (
                      <AuTr key={s.supervisora} i={i}>
                        <Td><span style={{ fontWeight: 500 }}>{s.supervisora}</span></Td>
                        <Td muted center>{s.revendedoras}</Td>
                        <Td>{R(s.baixado)}</Td>
                        <Td muted>{R(s.preBaixa)}</Td>
                        <Td><span style={{ fontWeight: 600 }}>{R(s.total)}</span></Td>
                        <Td center>
                          {s.abaixoMin > 0
                            ? <Badge label={String(s.abaixoMin)} variant="alerta" />
                            : <span style={{ color: 'var(--au-text-muted)' }}>—</span>}
                        </Td>
                        <Td center>
                          {s.zeradas > 0
                            ? <Badge label={String(s.zeradas)} variant="alerta" />
                            : <span style={{ color: 'var(--au-text-muted)' }}>—</span>}
                        </Td>
                      </AuTr>
                    ))}
                  </AuTable>
                )}

                {/* ── Acertos do mês ── */}
                {tab === 'acertos' && (
                  <AuTable
                    headers={['Nome', 'Supervisora', 'Data', 'Status', 'Dias ciclo', 'Valor']}
                    empty={metrics.rowsAcertosMes.length === 0 ? `Nenhum acerto em ${mesLabel}` : undefined}
                  >
                    {metrics.rowsAcertosMes.map((r, i) => (
                      <AuTr key={i} i={i}>
                        <Td><span style={{ fontWeight: 500 }}>{r.nome}</span></Td>
                        <Td muted>{r.supervisora}</Td>
                        <Td muted>{r.data}</Td>
                        <Td><Badge label={r.status} variant={statusVariant(r.status)} /></Td>
                        <Td center>
                          <span style={{ color: r.diasCiclo > 30 ? '#C4985A' : 'var(--au-text-muted)', fontWeight: r.diasCiclo > 30 ? 600 : 400 }}>
                            {r.diasCiclo}d
                          </span>
                        </Td>
                        <Td><span style={{ fontWeight: 500 }}>{R(r.valor)}</span></Td>
                      </AuTr>
                    ))}
                  </AuTable>
                )}

                {/* ── Alertas ── */}
                {tab === 'alertas' && (
                  <div className="flex flex-col gap-4">
                    {/* Baixados com zero */}
                    <div>
                      <div className="px-4 py-2.5 rounded-t-xl flex items-center gap-2" style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderBottom: 'none' }}>
                        <AlertTriangle size={14} color="#B91C1C" />
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#991B1B', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
                          Baixados com zero vendas — {metrics.rowsBxZero.length} pedido(s)
                        </span>
                      </div>
                      <AuTable headers={['Nome', 'Supervisora', 'Pedido', 'Valor maleta', 'Data baixa']}
                               empty={metrics.rowsBxZero.length === 0 ? `Nenhum pedido baixado com zero vendas em ${mesLabel}` : undefined}>
                        {metrics.rowsBxZero.map((r, i) => (
                          <AuTr key={i} i={i}>
                            <Td><span style={{ fontWeight: 500 }}>{r.nome}</span></Td>
                            <Td muted>{r.supervisora}</Td>
                            <Td muted>{r.codigoPedido}</Td>
                            <Td>{R(r.valorMaleta)}</Td>
                            <Td muted>{r.dataBaixa}</Td>
                          </AuTr>
                        ))}
                      </AuTable>
                    </div>

                    {/* Postergados */}
                    {metrics.rowsPostergados.length > 0 && (
                      <div>
                        <div className="px-4 py-2.5 rounded-t-xl flex items-center gap-2" style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderBottom: 'none' }}>
                          <span style={{ fontSize: 13 }}>⏰</span>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#92400E', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
                            Postergados (+30 dias) — {metrics.rowsPostergados.length}
                          </span>
                        </div>
                        <AuTable headers={['Nome', 'Supervisora', 'Status', 'Criação', 'Acerto prev.', 'Dias']}>
                          {metrics.rowsPostergados.map((r, i) => (
                            <AuTr key={i} i={i}>
                              <Td><span style={{ fontWeight: 500 }}>{r.nome}</span></Td>
                              <Td muted>{r.supervisora}</Td>
                              <Td><Badge label={r.status} variant={statusVariant(r.status)} /></Td>
                              <Td muted>{r.criacao}</Td>
                              <Td muted>{r.acertoPrev}</Td>
                              <Td center><span style={{ fontWeight: 700, color: '#C4985A' }}>{r.dias}d</span></Td>
                            </AuTr>
                          ))}
                        </AuTable>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </>
        )}
      </main>
    </div>
  )
}
