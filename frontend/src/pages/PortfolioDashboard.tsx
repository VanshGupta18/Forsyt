// Route: "/portfolio-exposure" (Portfolio Exposure & GPR Analytics). An
// illustrative page: live GPR/stress/market tiles at the top, then a
// regime-driven sector-sensitivity table and a GPR history chart. The
// sample allocation and scenario tables further down are static demo data
// (no real holdings are connected yet) — search for "Demo" in this file.
import { useMemo, useState, type ChangeEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import Reveal from '../components/Reveal'
import ExplainPopover from '../components/ExplainPopover'
import GprHistoryChart from '../components/GprHistoryChart'
import ApiErrorBanner from '../components/ApiErrorBanner'
import MarketTicker from '../components/MarketTicker'
import {
  analyzePortfolio,
  fetchPagePortfolio,
  fetchSectorBetas,
  formatCorridorName,
  formatPrice,
  orderMarketQuotes,
  type GprPanels,
  type PortfolioAnalysis,
  type PortfolioHolding,
  type SectorBeta,
} from '../lib/api'

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
import { portfolioStressContext } from '../lib/portfolioCopy'
import { queryKeys } from '../lib/queryClient'

export default function PortfolioDashboard() {
  const [searchParams] = useSearchParams()
  const stressParam = searchParams.get('stress')
  const corridorParam = searchParams.get('corridor')

  const { data, error, isLoading, refetch } = useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: fetchPagePortfolio,
  })

  const gpr = data?.gpr_current?.gpr_index ?? null
  const gprDate = data?.gpr_current?.date ?? null
  const dual = data?.dual_signal ?? null
  const quotes = orderMarketQuotes(data?.quotes?.quotes ?? [])
  const quotesLoading = isLoading && !quotes.length

  const panels = data?.gpr_panels
  const joint = dual?.joint_stress
  const geo = dual?.geopolitical
  const nifty = quotes.find((q) => q.key === 'nifty')
  const usdInr = quotes.find((q) => q.key === 'usd_inr')

  const context = useMemo(
    () => portfolioStressContext(stressParam, corridorParam, geo?.regime),
    [stressParam, corridorParam, geo?.regime],
  )

  const { data: betas } = useQuery({
    queryKey: ['portfolio', 'sector-betas'],
    queryFn: fetchSectorBetas,
    staleTime: 1000 * 60 * 60,
  })

  const fromStressMonitor = Boolean(stressParam || corridorParam)

  return (
    <div className="px-margin-page max-w-container-max mx-auto py-8 space-y-6">
      {fromStressMonitor ? (
        <div className="corridor-panel border-l-4 border-[var(--corridor-accent-watch)] p-4">
          <p className="corridor-kicker">From market stress monitor</p>
          <h2 className="corridor-headline text-base mt-1">{context.title}</h2>
          <p className="text-sm text-corridor-muted mt-2">{context.detail}</p>
          <Link to="/macroeconomics" className="text-xs text-corridor-muted underline hover:text-white mt-2 inline-block">
            ← Back to stress monitor
          </Link>
        </div>
      ) : (
        <div className="rounded-lg border border-[#f59e0b]/40 bg-[#f59e0b]/10 px-4 py-3 text-sm text-[#f59e0b] flex flex-wrap items-center justify-between gap-2">
          <span>Holdings analysis is illustrative — live GPR and dual-signal context below.</span>
          <Link to="/quality" className="text-white underline text-xs">Platform quality metrics →</Link>
        </div>
      )}

      <MarketTicker quotes={quotes} loading={quotesLoading} />

      {error instanceof Error && (
        <ApiErrorBanner message={`Portfolio data: ${error.message}`} onRetry={() => void refetch()} />
      )}

      <Reveal>
        <header className="glass-card p-6">
          <span className="eyebrow-badge mb-3 inline-flex">
            <span className="eyebrow-dot" />
            Live stress context
          </span>
          <h1 className="text-xl text-white font-semibold mb-2">Portfolio Exposure &amp; GPR Analytics</h1>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4 mt-4">
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">News risk score</div>
              <div className="text-2xl font-bold text-white">{gpr ?? '—'}</div>
              <div className="text-xs text-gray-400">{gprDate ? `As of ${gprDate}` : geo?.regime}</div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">Combined stress</div>
              <div className="text-2xl font-bold text-white">{joint?.stress_score ?? '—'}</div>
              <div className="text-xs text-gray-400">{joint?.stress_regime ?? '—'}</div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">NIFTY 50</div>
              <div className="text-2xl font-bold text-white">{nifty ? formatPrice(nifty.price, nifty.currency) : '—'}</div>
              <div className="text-xs text-gray-400">{nifty ? `${nifty.change_pct >= 0 ? '+' : ''}${nifty.change_pct}%` : '—'}</div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">USD/INR</div>
              <div className="text-2xl font-bold text-white">{usdInr ? formatPrice(usdInr.price, usdInr.currency) : '—'}</div>
              <div className="text-xs text-gray-400">
                {usdInr ? `${usdInr.change_pct >= 0 ? '+' : ''}${usdInr.change_pct}% · dominant risk channel` : '—'}
              </div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">Top trade route</div>
              <div className="text-2xl font-bold text-white truncate">{formatCorridorName(geo?.top_corridor) ?? '—'}</div>
              <div className="text-xs text-gray-400">Highest-risk corridor</div>
            </div>
          </div>
        </header>
      </Reveal>

      {panels && (panels.threats_acts || panels.risk_composition || panels.oil_gpr) && (
        <Reveal>
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {panels.threats_acts && <ThreatsActsPanel data={panels.threats_acts} />}
            {panels.risk_composition && <RiskCompositionPanel data={panels.risk_composition} />}
            {panels.oil_gpr && <OilGprPanel data={panels.oil_gpr} />}
          </section>
        </Reveal>
      )}

      <Reveal>
        <section className="glass-card p-5">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-base font-semibold text-white">Sector sensitivity · fitted betas</h2>
            {betas?.betas_source && (
              <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded ${betas.betas_source === 'fitted' ? 'bg-corridor-clear/20 text-corridor-clear' : 'bg-white/10 text-gray-400'}`}>
                {betas.betas_source === 'fitted' ? 'trained' : 'prior'}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Estimated from ~19 years of weekly sector returns regressed on GPR, oil (Brent) and INR shocks.
            Each chip is the fitted loading on that channel — <span className="text-corridor-alert">+ = headwind</span>,{' '}
            <span className="text-corridor-clear">− = tailwind</span>. INR is the dominant channel.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(betas?.sectors ?? []).map((row) => (
              <SectorBetaCard key={row.sector} row={row} />
            ))}
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="glass-card p-5">
          <h2 className="text-base font-semibold text-white mb-4">Historical news risk index</h2>
          <GprHistoryChart history={data?.gpr_history?.history ?? []} />
        </section>
      </Reveal>

      <Reveal>
        <PortfolioAnalyzer />
      </Reveal>

      <p className="text-[10px] text-gray-500 text-center">
        Sector tilts are educational context from live GPR regime — not investment advice.
      </p>
    </div>
  )
}

const SAMPLE_HOLDINGS = `Ticker,Qty
RELIANCE.NS,40
INFY.NS,60
HDFCBANK.NS,50
MARUTI.NS,10
SUNPHARMA.NS,30`

function bandClass(band: string): string {
  if (band === 'High') return 'text-corridor-alert'
  if (band === 'Elevated') return 'text-[#f59e0b]'
  if (band === 'Moderate') return 'text-corridor-watch'
  return 'text-corridor-clear'
}

function tiltColor(tilt: 'headwind' | 'tailwind' | 'neutral'): string {
  if (tilt === 'headwind') return 'text-corridor-alert'
  if (tilt === 'tailwind') return 'text-corridor-clear'
  return 'text-gray-500'
}

function tiltWord(tilt: 'headwind' | 'tailwind' | 'neutral'): string {
  if (tilt === 'headwind') return 'Headwind'
  if (tilt === 'tailwind') return 'Tailwind'
  return 'Neutral'
}

function SectorBetaCard({ row }: { row: SectorBeta }) {
  return (
    <div className="bg-[#0d0d0d] p-4 border border-white/5">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-sm text-white font-medium">{row.sector}</span>
        <span className={`text-[10px] uppercase font-semibold shrink-0 ${tiltColor(row.tilt)}`}>
          {tiltWord(row.tilt)}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {row.channels.map((c) => (
          <span
            key={c.channel}
            className={`text-[11px] px-1.5 py-0.5 rounded bg-white/5 ${tiltColor(c.tilt)}`}
            title={`${c.label} loading`}
          >
            {c.label} {c.loading > 0 ? '+' : ''}{c.loading}
          </span>
        ))}
      </div>
    </div>
  )
}

function PortfolioAnalyzer() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<PortfolioAnalysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function run(csv: string) {
    setBusy(true)
    setErr(null)
    try {
      setResult(await analyzePortfolio(csv))
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'analysis failed')
    } finally {
      setBusy(false)
    }
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    file.text().then((t) => {
      setText(t)
      void run(t)
    })
  }

  const overlayHoldings = (result?.holdings ?? []).filter((h) => h.overlay)

  return (
    <div className="space-y-6">
    <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div className="card-lift glass-card p-5 lg:col-span-5">
        <h2 className="text-base font-semibold text-white mb-1">Your holdings → GPR exposure</h2>
        <p className="text-sm text-gray-400 mb-3">
          Paste holdings (<code>TICKER, qty</code> per line) or upload your broker's holdings
          CSV. Nothing is stored — exposure is computed on the fly.
        </p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          placeholder={SAMPLE_HOLDINGS}
          className="w-full bg-[#0d0d0d] border border-white/10 rounded p-3 text-sm text-white font-mono"
        />
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <button
            onClick={() => void run(text || SAMPLE_HOLDINGS)}
            disabled={busy}
            className="bg-primary text-black text-sm font-semibold px-4 py-2 rounded disabled:opacity-50"
          >
            {busy ? 'Analysing…' : 'Analyse exposure'}
          </button>
          <label className="text-xs text-gray-400 underline cursor-pointer">
            Upload CSV
            <input type="file" accept=".csv,text/csv" onChange={onFile} className="hidden" />
          </label>
          <button
            onClick={() => setText(SAMPLE_HOLDINGS)}
            className="text-xs text-gray-500 underline"
          >
            Use sample
          </button>
          <span className="text-[10px] text-gray-600" title="Broker OAuth import is on the roadmap">
            Connect Zerodha · soon
          </span>
        </div>
        {err && <p className="text-xs text-corridor-alert mt-2">{err}</p>}
      </div>

      <div className="card-lift glass-card p-5 lg:col-span-7">
        {!result ? (
          <p className="text-sm text-gray-400">
            Run an analysis to see your portfolio's geopolitical-risk score, the sectors and
            corridors driving it, and how it moves under an energy-supply shock.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <div className="text-xs text-gray-500 uppercase mb-1 flex items-center gap-2">
                  Portfolio GPR risk
                  <ExplainPopover explain={result.explain} align="left" />
                </div>
                <div className={`text-4xl font-bold ${bandClass(result.risk_band)}`}>
                  {result.risk_score}
                  <span className="text-base font-medium ml-2">{result.risk_band}</span>
                </div>
              </div>
              <div className="text-right text-xs text-gray-400">
                <div className="flex items-center justify-end gap-2">
                  <span>News risk {result.gpr_index} · as of {result.as_of ?? '—'}</span>
                  {result.betas_source && (
                    <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded ${result.betas_source === 'fitted' ? 'bg-corridor-clear/20 text-corridor-clear' : 'bg-white/10 text-gray-400'}`}>
                      {result.betas_source === 'fitted' ? 'trained betas' : 'prior betas'}
                    </span>
                  )}
                </div>
                <div className="mt-1">
                  Pressures — GPR {result.pressures?.broad} · Oil {result.pressures?.energy} · INR {result.pressures?.fx ?? '—'} · Trade {result.pressures?.trade ?? '—'}
                </div>
                {result.gpr_oil_index != null && (
                  <div className="mt-0.5">India gpr_oil index {result.gpr_oil_index}</div>
                )}
              </div>
            </div>

            <div>
              <div className="text-xs text-gray-500 uppercase mb-2">Exposure by sector</div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-white/10">
                    <th className="pb-1 text-left">Sector</th>
                    <th className="pb-1 text-right">Weight</th>
                    <th className="pb-1 text-right">Risk contribution</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {result.sectors.map((s) => (
                    <tr key={s.sector}>
                      <td className="py-1.5">{s.sector}</td>
                      <td className="py-1.5 text-right">{Math.round(s.weight * 100)}%</td>
                      <td className={`py-1.5 text-right ${s.contribution < 0 ? 'text-corridor-clear' : 'text-white'}`}>
                        {s.contribution > 0 ? '+' : ''}{s.contribution}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {result.scenarios.map((sc) => (
                <div key={sc.name} className="bg-[#0d0d0d] p-3 border border-white/5">
                  <div className="text-xs text-gray-400">{sc.name}</div>
                  <div className="text-lg font-semibold text-white">
                    {sc.score}
                    <span className={`text-xs ml-2 ${sc.delta >= 0 ? 'text-corridor-alert' : 'text-corridor-clear'}`}>
                      {sc.delta >= 0 ? '+' : ''}{sc.delta}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {(result.drivers?.energy_corridor || result.drivers?.trade_corridor) && (
              <p className="text-xs text-gray-500">
                Live route drivers: energy → {result.drivers?.energy_corridor ?? '—'}, trade → {result.drivers?.trade_corridor ?? '—'}.
              </p>
            )}
            {result.note && <p className="text-[10px] text-gray-600">{result.note}</p>}
          </div>
        )}
      </div>
    </section>

    {overlayHoldings.length > 0 && (
      <section className="glass-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
          <h2 className="text-base font-semibold text-white">Per-holding · GPR vs price &amp; joint stress</h2>
          <div className="flex items-center gap-4 text-[10px] font-mono uppercase tracking-wide text-gray-500">
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-px" style={{ background: '#f5b800' }} /> GPR</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-px" style={{ background: '#38bdf8' }} /> price</span>
          </div>
        </div>
        <p className="text-sm text-gray-400 mb-4">
          Native GPR index and each stock&apos;s own price, rebased to 100 over the index window. Joint
          stress = 60% GPR percentile + 40% that stock&apos;s volatility percentile (same blend as the
          NIFTY dual-signal). ρ is the correlation of daily GPR moves with the stock&apos;s daily return.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {overlayHoldings.map((h) => (
            <HoldingTile key={h.ticker} holding={h} />
          ))}
        </div>
      </section>
    )}
    </div>
  )
}

function jointColor(band: string): string {
  if (band === 'High stress') return '#ff3333'
  if (band === 'Watch') return '#f5b800'
  return '#00c853'
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

// Two rebased lines (GPR + price) on a shared y-scale — the World-Monitor
// stat-tile look: label, mini graph, then a tight tabular-nums stat row.
function OverlaySparkline({ holding }: { holding: PortfolioHolding }) {
  const pts = holding.overlay?.series ?? []
  if (pts.length < 2) return <div style={{ height: 56 }} aria-hidden />
  const w = 240
  const h = 56
  const pad = 3
  const x = (i: number) => pad + (i / (pts.length - 1)) * (w - pad * 2)
  // Each line gets its OWN y-scale: GPR (identical, spiky, market-wide) and the
  // stock's price move on wildly different ranges — a shared axis would flatten
  // the price line and make every tile look the same. Independent scales let
  // both fill the tile so each holding's price path is actually visible.
  const scale = (vals: number[]) => {
    const mn = Math.min(...vals)
    const range = Math.max(...vals) - mn || 1
    return (v: number) => pad + (h - pad * 2) - ((v - mn) / range) * (h - pad * 2)
  }
  const yGpr = scale(pts.map((p) => p.gpr))
  const yPx = scale(pts.map((p) => p.px))
  const line = (key: 'gpr' | 'px') =>
    pts.map((p, i) => `${x(i)},${(key === 'gpr' ? yGpr : yPx)(p[key])}`).join(' ')
  const priceUp = (holding.overlay?.price_change_pct ?? 0) >= 0
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: h }} preserveAspectRatio="none" aria-hidden>
      <polyline fill="none" stroke="#f5b800" strokeOpacity={0.7} strokeWidth={1.25} points={line('gpr')} />
      <polyline fill="none" stroke={priceUp ? '#38bdf8' : '#ff6b6b'} strokeWidth={1.75} points={line('px')} />
    </svg>
  )
}

function HoldingTile({ holding }: { holding: PortfolioHolding }) {
  const o = holding.overlay!
  const dpx = o.price_change_pct
  return (
    <div className="bg-[#0d0d0d] border border-white/5 p-3 font-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="min-w-0">
          <div className="text-sm text-white font-semibold truncate">{holding.ticker}</div>
          <div className="text-[10px] text-gray-500 truncate">{holding.sector}</div>
        </div>
        <span
          className="text-[9px] uppercase font-semibold px-1.5 py-0.5 rounded shrink-0"
          style={{ color: jointColor(o.joint_band), background: `${jointColor(o.joint_band)}1f` }}
        >
          {o.joint_band}
        </span>
      </div>
      <OverlaySparkline holding={holding} />
      <div className="grid grid-cols-3 gap-1 mt-2 text-center">
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Joint</div>
          <div className="text-sm" style={{ color: jointColor(o.joint_band) }}>{o.joint_stress}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Δ price</div>
          <div className="text-sm" style={{ color: dpx >= 0 ? '#38bdf8' : '#ff6b6b' }}>
            {dpx >= 0 ? '+' : ''}{dpx}%
          </div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">ρ GPR</div>
          <div className="text-sm text-gray-300">{o.corr ?? '—'}</div>
        </div>
      </div>
      <div className="mt-1.5 text-[9px] text-gray-600 flex justify-between items-center">
        <span>wt {Math.round(holding.weight * 100)}%</span>
        <span className="flex items-center gap-2">
          <span>vol pctile {o.vol_percentile}</span>
          <ExplainPopover explain={holding.explain} label="risk" />
        </span>
      </div>
    </div>
  )
}
