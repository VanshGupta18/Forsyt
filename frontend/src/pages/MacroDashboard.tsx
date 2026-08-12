import { useCallback, useEffect, useState } from 'react'
import Reveal from '../components/Reveal'
import GprHistoryChart from '../components/GprHistoryChart'
import MarketTicker from '../components/MarketTicker'
import MarketSparkline from '../components/MarketSparkline'
import ApiErrorBanner from '../components/ApiErrorBanner'
import {
  fetchDualSignal,
  fetchGprCurrent,
  fetchMarketIndicators,
  fetchMarketQuotes,
  formatPrice,
  MARKET_SYMBOL_LABELS,
  MARKET_SYMBOL_ORDER,
  orderMarketQuotes,
  type DualSignalPayload,
  type MarketQuote,
} from '../lib/api'

const KPI_KEYS = MARKET_SYMBOL_ORDER

function regimeTone(regime?: string) {
  const r = (regime ?? '').toUpperCase()
  if (r.includes('HIGH') || r.includes('ELEVATED') || r.includes('WATCH')) return 'text-[#EF4444]'
  if (r.includes('LOW') || r.includes('CALM') || r.includes('NORMAL')) return 'text-[#10B981]'
  return 'text-[#f59e0b]'
}

function SignalDial({
  title,
  subtitle,
  primary,
  primaryLabel,
  regime,
  rows,
}: {
  title: string
  subtitle: string
  primary: string
  primaryLabel: string
  regime?: string
  rows: Array<{ label: string; value: string }>
}) {
  return (
    <div className="card-lift glass-panel rounded-xl p-5 h-full flex flex-col gap-4">
      <div>
        <h2 className="text-white font-semibold">{title}</h2>
        <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      </div>
      <div className="rounded-lg border border-white/10 bg-[#0A101C]/60 p-4">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{primaryLabel}</span>
        <div className="flex items-end justify-between gap-3 mt-1">
          <span className="text-3xl font-bold text-white tabular-nums">{primary}</span>
          {regime && <span className={`text-sm font-semibold ${regimeTone(regime)}`}>{regime}</span>}
        </div>
      </div>
      <div className="space-y-2 text-sm mt-auto">
        {rows.map((row) => (
          <div key={row.label} className="flex justify-between border-b border-white/5 pb-2 last:border-0">
            <span className="text-gray-400">{row.label}</span>
            <span className="text-white tabular-nums">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function MacroDashboard() {
  const [dual, setDual] = useState<DualSignalPayload | null>(null)
  const [gprCurrent, setGprCurrent] = useState<number | null>(null)
  const [quotes, setQuotes] = useState<MarketQuote[]>([])
  const [indicators, setIndicators] = useState<{ trailing_vol_22d?: number | null; return_7d_pct?: number | null } | null>(null)
  const [dualError, setDualError] = useState<string | null>(null)
  const [quotesError, setQuotesError] = useState<string | null>(null)
  const [quotesLoading, setQuotesLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const loadQuotes = useCallback(() => {
    setQuotesLoading(true)
    setQuotesError(null)
    fetchMarketQuotes()
      .then((p) => {
        setQuotes(orderMarketQuotes(p.quotes ?? []))
        if (p.errors?.length) setQuotesError(p.errors.join(' · '))
      })
      .catch((e: Error) => {
        setQuotes([])
        setQuotesError(e.message)
      })
      .finally(() => setQuotesLoading(false))
    fetchMarketIndicators('nifty')
      .then(setIndicators)
      .catch(() => undefined)
  }, [])

  const loadDual = useCallback((refresh = false) => {
    setDualError(null)
    fetchDualSignal(refresh)
      .then(setDual)
      .catch((e: Error) => setDualError(e.message))
  }, [])

  useEffect(() => {
    loadQuotes()
    loadDual(false)
    fetchGprCurrent()
      .then((g) => setGprCurrent(g.gpr_index ?? null))
      .catch(() => undefined)
  }, [loadDual, loadQuotes])

  const refreshAll = () => {
    setRefreshing(true)
    loadQuotes()
    loadDual(true)
    fetchGprCurrent()
      .then((g) => setGprCurrent(g.gpr_index ?? null))
      .catch(() => undefined)
    setTimeout(() => setRefreshing(false), 800)
  }

  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility
  const joint = dual?.joint_stress
  const analog = dual?.historical_analog
  const volUnavailable = vol?.available === false
  const gprDisplay = geo?.gpr_index ?? gprCurrent
  const nifty = quotes.find((q) => q.key === 'nifty')

  return (
    <>
      {(dual || gprDisplay != null || nifty) && (
        <div className="border-b border-[#3b82f6]/30 bg-[#0A101C]/80 py-3">
          <div className="max-w-[1600px] mx-auto px-6 text-sm text-gray-300 flex flex-wrap gap-6 items-center">
            <span>NIFTY 50 · as of <strong className="text-white">{nifty?.as_of ?? geo?.as_of ?? '—'}</strong></span>
            <span>Price: <strong className="text-white">{nifty ? formatPrice(nifty.price, nifty.currency) : '—'}</strong></span>
            <span>GPR: <strong className="text-white">{gprDisplay ?? '—'}</strong>{geo?.regime ? ` (${geo.regime})` : ''}</span>
            <span>Vol (5d): <strong className="text-white">{volUnavailable ? 'N/A' : vol?.vol_forecast_5d != null ? `${vol.vol_forecast_5d}%` : '—'}</strong></span>
            <span>Joint stress: <strong className="text-white">{joint?.stress_score ?? '—'}</strong>{joint?.stress_regime ? ` (${joint.stress_regime})` : ''}</span>
            {joint?.stress_score != null && (
              <div className="h-1.5 w-32 bg-[#111827] rounded-full overflow-hidden">
                <div className="h-full bg-[#b3202c]" style={{ width: `${joint.stress_score}%` }} />
              </div>
            )}
            <button type="button" onClick={refreshAll} disabled={refreshing} className="ml-auto text-xs px-3 py-1 rounded border border-white/20 hover:bg-white/5">
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>
      )}

      <MarketTicker quotes={quotes} loading={quotesLoading} />

      <div className="flex-grow max-w-[1600px] mx-auto w-full px-6 py-8 flex flex-col gap-6">
        {dualError && <ApiErrorBanner message={`Dual-signal: ${dualError}`} onRetry={() => loadDual(true)} />}
        {quotesError && <ApiErrorBanner message={`Market quotes partial: ${quotesError}`} onRetry={loadQuotes} />}

        <Reveal>
          <section className="flex flex-col lg:flex-row gap-6 justify-between items-start">
            <div className="max-w-2xl space-y-3">
              <span className="eyebrow-badge">
                <span className="eyebrow-dot" />
                NIFTY 50 · Dual-Signal Product
              </span>
              <h1 className="text-4xl font-bold text-white mb-2">Indian Macroeconomic Intelligence</h1>
              <p className="text-gray-400">
                Geopolitical risk and NIFTY volatility side by side — honest context, not a prediction engine.
                Market vol uses price data only; GPR comes from Indian news.
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-3 w-full lg:w-auto lg:max-w-4xl">
              {KPI_KEYS.map((k) => {
                const q = quotes.find((x) => x.key === k)
                return (
                  <div key={k} className={`card-lift glass-panel rounded-xl p-4 min-w-[140px] ${k === 'nifty' ? 'ring-1 ring-[#3b82f6]/40' : ''}`}>
                    <div className="flex justify-between items-start mb-2 gap-1">
                      <span className="text-xs text-gray-400 font-medium">{q?.label ?? MARKET_SYMBOL_LABELS[k]}</span>
                      {q && (
                        <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${q.change_pct >= 0 ? 'text-[#10B981] bg-[#10B981]/10' : 'text-[#EF4444] bg-[#EF4444]/10'}`}>
                          {q.change_pct >= 0 ? '+' : ''}{q.change_pct}%
                        </span>
                      )}
                    </div>
                    <div className="text-lg font-bold text-white">{q ? formatPrice(q.price, q.currency) : quotesLoading ? '…' : '—'}</div>
                    <div className="text-xs text-gray-500">{q?.as_of ?? (quotesLoading ? 'Loading' : 'Unavailable')}{q?.stale ? ' · stale' : ''}</div>
                  </div>
                )
              })}
            </div>
          </section>
        </Reveal>

        <Reveal>
          <section className="card-lift glass-panel rounded-xl p-5">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-white font-semibold text-lg">Joint stress</h2>
                <p className="text-xs text-gray-500 mt-1">60% geo percentile + 40% vol percentile</p>
              </div>
              {dual?.disclaimer && <p className="text-[10px] text-gray-600 max-w-md">{dual.disclaimer}</p>}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
              <div className="md:col-span-1 flex flex-col items-center justify-center p-4">
                <div className="relative w-36 h-36 rounded-full border-4 border-[#1f2937] flex items-center justify-center">
                  <div
                    className="absolute inset-0 rounded-full"
                    style={{
                      background: `conic-gradient(#b3202c ${joint?.stress_score ?? 0}%, transparent 0)`,
                      mask: 'radial-gradient(farthest-side, transparent calc(100% - 8px), #000 calc(100% - 7px))',
                      WebkitMask: 'radial-gradient(farthest-side, transparent calc(100% - 8px), #000 calc(100% - 7px))',
                    }}
                  />
                  <div className="text-center z-10">
                    <div className="text-3xl font-bold text-white tabular-nums">{joint?.stress_score ?? '—'}</div>
                    <div className={`text-xs font-semibold mt-1 ${regimeTone(joint?.stress_regime)}`}>{joint?.stress_regime ?? '—'}</div>
                  </div>
                </div>
              </div>
              <div className="md:col-span-2 space-y-3 text-sm text-gray-300">
                <p>{joint?.narrative ?? (dual ? 'Loading joint stress…' : 'Dual-signal loading…')}</p>
                {volUnavailable && (
                  <p className="text-xs text-[#f59e0b] border border-[#f59e0b]/30 rounded p-2">{vol?.reason ?? joint?.narrative}</p>
                )}
                {analog && (analog.sample_days ?? 0) > 0 && (
                  <div className="text-xs text-gray-400 border-t border-white/5 pt-3">
                    <p className="text-gray-500 uppercase tracking-wider mb-1">Historical analog</p>
                    <p>{analog.query}</p>
                    <p className="mt-1">Sample: {analog.sample_days} days · median vol {analog.nifty_vol_median ?? '—'}% · median return {analog.nifty_return_median ?? '—'}%</p>
                  </div>
                )}
              </div>
            </div>
          </section>
        </Reveal>

        <Reveal>
          <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <SignalDial
              title="Geopolitical signal"
              subtitle="Forsyt GPR from Indian news"
              primary={gprDisplay != null ? String(gprDisplay) : '—'}
              primaryLabel="GPR index"
              regime={geo?.regime}
              rows={[
                {
                  label: '7d change',
                  value: geo?.change_7d_pct != null ? `${geo.change_7d_pct > 0 ? '+' : ''}${geo.change_7d_pct}%` : '—',
                },
                { label: '7d MA', value: geo?.gpr_7ma != null ? String(geo.gpr_7ma) : '—' },
                { label: '30d MA', value: geo?.gpr_30ma != null ? String(geo.gpr_30ma) : '—' },
                { label: 'Geo percentile', value: geo?.geo_percentile != null ? `${geo.geo_percentile}%` : '—' },
                { label: 'Top corridor', value: geo?.top_corridor ?? '—' },
              ]}
            />
            <SignalDial
              title="NIFTY volatility"
              subtitle="Market-only forecast (no GPR in model)"
              primary={volUnavailable ? 'N/A' : vol?.vol_forecast_5d != null ? `${vol.vol_forecast_5d}%` : '—'}
              primaryLabel="5-day vol forecast"
              regime={volUnavailable ? 'UNAVAILABLE' : vol?.regime}
              rows={[
                {
                  label: 'NIFTY spot',
                  value: nifty ? formatPrice(nifty.price, nifty.currency) : '—',
                },
                {
                  label: '7d return',
                  value:
                    indicators?.return_7d_pct != null
                      ? `${indicators.return_7d_pct > 0 ? '+' : ''}${indicators.return_7d_pct}%`
                      : vol?.return_7d_pct != null
                        ? `${vol.return_7d_pct > 0 ? '+' : ''}${vol.return_7d_pct}%`
                        : '—',
                },
                {
                  label: 'Trailing vol (22d)',
                  value:
                    vol?.trailing_vol_22d != null
                      ? `${vol.trailing_vol_22d}%`
                      : indicators?.trailing_vol_22d != null
                        ? `${indicators.trailing_vol_22d}%`
                        : '—',
                },
                {
                  label: 'High-vol probability',
                  value: !volUnavailable && vol?.high_vol_prob != null ? `${(vol.high_vol_prob * 100).toFixed(1)}%` : '—',
                },
                { label: 'Vol percentile', value: vol?.vol_percentile != null ? `${vol.vol_percentile}%` : '—' },
              ]}
            />
          </section>
        </Reveal>

        <Reveal>
          <section className="card-lift glass-panel rounded-xl p-5">
            <div className="flex flex-wrap justify-between items-center gap-3 mb-4">
              <div>
                <h2 className="text-white font-semibold text-lg">NIFTY 50 · 3 month</h2>
                <p className="text-xs text-gray-500">Live price history from market data</p>
              </div>
              {nifty && (
                <div className="text-right">
                  <div className="text-2xl font-bold text-white tabular-nums">{formatPrice(nifty.price, nifty.currency)}</div>
                  <div className={`text-sm ${nifty.change_pct >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                    {nifty.change_pct >= 0 ? '+' : ''}{nifty.change_pct}% today
                  </div>
                </div>
              )}
            </div>
            <MarketSparkline symbol="nifty" period="3mo" height={280} title="NIFTY 50" />
          </section>
        </Reveal>

        {(geo?.driving_events?.length ?? 0) > 0 && (
          <Reveal>
            <section className="card-lift glass-panel rounded-xl p-5">
              <h2 className="text-white font-semibold text-sm mb-3">Driving events (geo signal)</h2>
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                {geo!.driving_events!.map((ev, i) => (
                  <li key={ev.link ?? `${ev.title}-${i}`} className="border border-white/5 rounded-lg p-3">
                    <a href={ev.link} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline font-medium">{ev.title}</a>
                    <div className="text-gray-500 mt-1">{ev.source} · {ev.nlp_themes || '—'}</div>
                  </li>
                ))}
              </ul>
            </section>
          </Reveal>
        )}

        <Reveal>
          <section className="card-lift glass-panel rounded-xl p-5 flex flex-col">
            <div className="flex justify-between items-center mb-2">
              <div>
                <h2 className="text-white font-semibold">Forsyt GPR · news context</h2>
                <p className="text-xs text-gray-500">Index warming up — early August baseline</p>
              </div>
            </div>
            <GprHistoryChart height={320} />
          </section>
        </Reveal>
      </div>
    </>
  )
}
