// Portfolio analyzer — paste/upload holdings → GPR exposure, sector tilts,
// scenario shock and per-holding GPR-vs-price tiles. Stateless (nothing is
// stored); computed on the fly via POST /api/portfolio/analyze. Lives on the
// Markets page as the "your holdings" section.
import { useEffect, useState, type ChangeEvent } from 'react'
import {
  analyzePortfolio,
  fetchPortfolioSummary,
  isModelGenerated,
  type AiSummary,
  type PortfolioAnalysis,
  type PortfolioHolding,
} from '../lib/api'
import SectorExposure from './SectorExposure'
import ExplainPopover from './ExplainPopover'
import HoldingChartModal from './HoldingChartModal'

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

// AI (Gemini) explainer for the whole portfolio, refetched whenever the
// analysis changes. Falls back to a deterministic narrative server-side.
function PortfolioAiSummary({ analysis }: { analysis: PortfolioAnalysis }) {
  const [summary, setSummary] = useState<AiSummary | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    setSummary(null)
    setError(false)
    fetchPortfolioSummary(analysis)
      .then((s) => alive && setSummary(s))
      .catch(() => alive && setError(true))
    return () => {
      alive = false
    }
  }, [analysis])

  return (
    <div className="border-t border-white/10 pt-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] uppercase tracking-wide text-corridor-muted">AI summary</span>
        {isModelGenerated(summary?.source) && (
          <span className="text-[8px] uppercase px-1 py-0.5 rounded bg-corridor-clear/20 text-corridor-clear" title={`Written by the ${summary?.source} model from the attribution numbers`}>
            {summary?.source}
          </span>
        )}
        {(summary?.source === 'deterministic' || summary?.source === 'fallback') && (
          <span className="text-[8px] uppercase px-1 py-0.5 rounded bg-white/10 text-gray-400" title="Generated from the attribution numbers (no model configured)">
            computed
          </span>
        )}
      </div>
      {error ? (
        <p className="text-xs text-corridor-muted">Summary unavailable right now.</p>
      ) : summary ? (
        <p className="text-sm text-gray-300 leading-relaxed">{summary.summary}</p>
      ) : (
        <div className="space-y-1.5 animate-pulse">
          <div className="h-3 bg-white/5 rounded w-full" />
          <div className="h-3 bg-white/5 rounded w-11/12" />
          <div className="h-3 bg-white/5 rounded w-4/5" />
        </div>
      )}
      <p className="mt-1.5 text-[9px] text-gray-600">Explanatory context, not investment advice.</p>
    </div>
  )
}

export default function PortfolioAnalyzer() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<PortfolioAnalysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<PortfolioHolding | null>(null)

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

            <SectorExposure sectors={result.sectors} holdings={result.holdings} />

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

            <PortfolioAiSummary analysis={result} />

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
            <HoldingTile key={h.ticker} holding={h} onExpand={() => setExpanded(h)} />
          ))}
        </div>
      </section>
    )}

    {expanded && <HoldingChartModal holding={expanded} onClose={() => setExpanded(null)} />}
    </div>
  )
}

function jointColor(band: string): string {
  if (band === 'High stress') return '#ff3333'
  if (band === 'Watch') return '#f5b800'
  return '#00c853'
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

function HoldingTile({ holding, onExpand }: { holding: PortfolioHolding; onExpand: () => void }) {
  const o = holding.overlay!
  const dpx = o.price_change_pct
  return (
    <div
      className="group bg-[#0d0d0d] border border-white/5 p-3 font-mono cursor-pointer hover:border-white/20 hover:bg-white/[0.02] transition-colors"
      style={{ fontVariantNumeric: 'tabular-nums' }}
      role="button"
      tabIndex={0}
      aria-label={`Expand ${holding.ticker} chart`}
      onClick={onExpand}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onExpand()
        }
      }}
    >
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
          <span onClick={(e) => e.stopPropagation()}>
            <ExplainPopover explain={holding.explain} label="risk" />
          </span>
        </span>
      </div>
    </div>
  )
}
