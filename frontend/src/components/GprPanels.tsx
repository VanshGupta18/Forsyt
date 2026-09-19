// The three GPR "what's driving the risk" panels — Threats vs acts, Risk
// composition, and India oil-GPR — shown as a 3-up row. Rendered on both the
// Home page and the Portfolio Exposure dashboard.
import type { GprPanels } from '../lib/api'

type ThreatsActs = NonNullable<GprPanels['threats_acts']>
type RiskComposition = NonNullable<GprPanels['risk_composition']>
type OilGpr = NonNullable<GprPanels['oil_gpr']>

const EVENT_COLORS: Record<string, string> = {
  Military: '#ef4444',
  Terrorism: '#f97316',
  Diplomatic: '#38bdf8',
  Nuclear: '#a855f7',
  Sanctions: '#f5b800',
  'Coup/Regime': '#ec4899',
  'Civil war': '#14b8a6',
  Other: '#737373',
}

// A tiny single-series polyline sparkline for the GPR panels.
function Spark({ values, color, height = 40 }: { values: number[]; color: string; height?: number }) {
  const v = values.filter(Number.isFinite)
  if (v.length < 2) return <div style={{ height }} aria-hidden />
  const w = 200
  const pad = 2
  const min = Math.min(...v)
  const range = Math.max(...v) - min || 1
  const pts = v
    .map((val, i) => {
      const x = pad + (i / (v.length - 1)) * (w - pad * 2)
      const y = pad + (height - pad * 2) - ((val - min) / range) * (height - pad * 2)
      return `${x},${y}`
    })
    .join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${height}`} style={{ width: '100%', height }} preserveAspectRatio="none" aria-hidden>
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={pts} />
    </svg>
  )
}

// "What's driving the risk" — event-type mix as a single stacked bar + legend.
function RiskCompositionPanel({ data }: { data: RiskComposition }) {
  return (
    <div className="glass-card p-4 font-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <h3 className="text-sm font-semibold text-white">Risk composition</h3>
        <span className="text-[9px] uppercase text-gray-500">last {data.window_days}d</span>
      </div>
      <p className="text-[10px] text-gray-500 mb-3">Share of GPR by event type</p>
      <div className="flex h-3 w-full overflow-hidden rounded-sm mb-3">
        {data.items.map((it) => (
          <div
            key={it.type}
            title={`${it.type} ${it.share}%`}
            style={{ width: `${it.share}%`, background: EVENT_COLORS[it.type] ?? '#737373' }}
          />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {data.items.map((it) => (
          <div key={it.type} className="flex items-center justify-between text-[11px]">
            <span className="flex items-center gap-1.5 text-gray-300 truncate">
              <span className="inline-block w-2 h-2 rounded-sm shrink-0" style={{ background: EVENT_COLORS[it.type] ?? '#737373' }} />
              {it.type}
            </span>
            <span className="text-gray-400">{it.share}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Forward-looking threats vs realized acts — two gauge bars + a dual spark.
function ThreatsActsPanel({ data }: { data: ThreatsActs }) {
  const gauge = (label: string, value: number, pctile: number | null, color: string) => (
    <div className="mb-2">
      <div className="flex items-baseline justify-between text-[11px] mb-1">
        <span className="text-gray-300">{label}</span>
        <span className="text-white">{value}{pctile != null && <span className="text-gray-500"> · {pctile}pctile</span>}</span>
      </div>
      <div className="h-2 w-full bg-white/5 rounded-sm overflow-hidden">
        <div style={{ width: `${Math.min(pctile ?? 0, 100)}%`, background: color }} className="h-full" />
      </div>
    </div>
  )
  return (
    <div className="glass-card p-4 font-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <h3 className="text-sm font-semibold text-white">Threats vs acts</h3>
        <span className="text-[9px] uppercase text-gray-500">{data.as_of ?? ''}</span>
      </div>
      <p className="text-[10px] text-gray-500 mb-3">Forward-looking threats vs realized violence (bar = percentile)</p>
      {gauge('Threats', data.threats_index, data.threats_percentile, '#f5b800')}
      {gauge('Acts', data.acts_index, data.acts_percentile, '#ef4444')}
      <div className="mt-2 flex items-center gap-3 text-[9px] uppercase text-gray-500">
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-px" style={{ background: '#f5b800' }} />threats</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-px" style={{ background: '#ef4444' }} />acts</span>
      </div>
      <DualSpark
        a={data.spark.map((p) => p.threats ?? NaN)}
        b={data.spark.map((p) => p.acts ?? NaN)}
        colorA="#f5b800"
        colorB="#ef4444"
      />
    </div>
  )
}

// Two independently-scaled lines (threats + acts) sharing an x-axis.
function DualSpark({ a, b, colorA, colorB }: { a: number[]; b: number[]; colorA: string; colorB: string }) {
  const h = 40
  const w = 200
  const pad = 2
  const line = (vals: number[]) => {
    const v = vals.map((x) => (Number.isFinite(x) ? x : null))
    const finite = v.filter((x): x is number => x != null)
    if (finite.length < 2) return ''
    const min = Math.min(...finite)
    const range = Math.max(...finite) - min || 1
    return v
      .map((val, i) =>
        val == null ? null : `${pad + (i / (v.length - 1)) * (w - pad * 2)},${pad + (h - pad * 2) - ((val - min) / range) * (h - pad * 2)}`,
      )
      .filter(Boolean)
      .join(' ')
  }
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: h }} preserveAspectRatio="none" aria-hidden className="mt-1">
      <polyline fill="none" stroke={colorA} strokeWidth={1.5} strokeOpacity={0.85} points={line(a)} />
      <polyline fill="none" stroke={colorB} strokeWidth={1.5} points={line(b)} />
    </svg>
  )
}

// India oil-GPR channel: big number + 7d change + percentile + spark.
function OilGprPanel({ data }: { data: OilGpr }) {
  const up = (data.change_7d ?? 0) >= 0
  return (
    <div className="glass-card p-4 font-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <h3 className="text-sm font-semibold text-white">India oil-GPR</h3>
        <span className="text-[9px] uppercase text-gray-500">{data.as_of ?? ''}</span>
      </div>
      <p className="text-[10px] text-gray-500 mb-3">Energy-corridor geopolitical pressure on crude</p>
      <div className="flex items-end gap-3 mb-2">
        <span className="text-3xl font-bold text-white">{data.index}</span>
        {data.change_7d != null && (
          <span className="text-sm mb-1" style={{ color: up ? '#ef4444' : '#00c853' }}>
            {up ? '+' : ''}{data.change_7d} 7d
          </span>
        )}
      </div>
      {data.percentile != null && (
        <div className="text-[11px] text-gray-400 mb-2">{data.percentile} percentile of history</div>
      )}
      <Spark values={data.spark.map((p) => p.v ?? NaN)} color="#f97316" />
    </div>
  )
}

// The 3-up row. Renders nothing until at least one panel has data.
export default function GprPanelsRow({ panels }: { panels: GprPanels | undefined }) {
  if (!panels || !(panels.threats_acts || panels.risk_composition || panels.oil_gpr)) return null
  return (
    <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {panels.threats_acts && <ThreatsActsPanel data={panels.threats_acts} />}
      {panels.risk_composition && <RiskCompositionPanel data={panels.risk_composition} />}
      {panels.oil_gpr && <OilGprPanel data={panels.oil_gpr} />}
    </section>
  )
}
