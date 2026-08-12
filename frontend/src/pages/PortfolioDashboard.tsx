import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Reveal from '../components/Reveal'
import GprHistoryChart from '../components/GprHistoryChart'
import ApiErrorBanner from '../components/ApiErrorBanner'
import MarketTicker from '../components/MarketTicker'
import {
  fetchDualSignal,
  fetchGprCurrent,
  fetchMarketQuotes,
  formatPrice,
  orderMarketQuotes,
  type DualSignalPayload,
  type MarketQuote,
} from '../lib/api'

export default function PortfolioDashboard() {
  const [gpr, setGpr] = useState<number | null>(null)
  const [gprDate, setGprDate] = useState<string | null>(null)
  const [dual, setDual] = useState<DualSignalPayload | null>(null)
  const [dualError, setDualError] = useState<string | null>(null)
  const [quotes, setQuotes] = useState<MarketQuote[]>([])
  const [quotesLoading, setQuotesLoading] = useState(true)

  const load = useCallback(() => {
    fetchGprCurrent()
      .then((g) => {
        setGpr(g.gpr_index ?? null)
        setGprDate(g.date ?? null)
      })
      .catch(() => undefined)
    setDualError(null)
    fetchDualSignal(false)
      .then(setDual)
      .catch((e: Error) => setDualError(e.message))
    setQuotesLoading(true)
    fetchMarketQuotes()
      .then((p) => setQuotes(orderMarketQuotes(p.quotes ?? [])))
      .catch(() => setQuotes([]))
      .finally(() => setQuotesLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const joint = dual?.joint_stress
  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility
  const nifty = quotes.find((q) => q.key === 'nifty')
  const usdInr = quotes.find((q) => q.key === 'usd_inr')

  return (
    <div className="px-margin-page max-w-container-max mx-auto py-8 space-y-6">
      <div className="rounded-lg border border-[#f59e0b]/40 bg-[#f59e0b]/10 px-4 py-3 text-sm text-[#f59e0b] flex flex-wrap items-center justify-between gap-2">
        <span>Portfolio analytics — demo UI. GPR, dual-signal, and market quotes below are live.</span>
        <Link to="/quality" className="text-white underline text-xs">Platform quality metrics →</Link>
      </div>

      <MarketTicker quotes={quotes} loading={quotesLoading} />

      {dualError && <ApiErrorBanner message={`Dual-signal: ${dualError}`} onRetry={load} />}

      <Reveal>
        <header className="glass-card p-6">
          <span className="eyebrow-badge mb-3 inline-flex">
            <span className="eyebrow-dot" />
            Live GPR Context
          </span>
          <h1 className="text-xl text-white font-semibold mb-2">Portfolio Exposure &amp; GPR Analytics</h1>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">Forsyt GPR</div>
              <div className="text-2xl font-bold text-white">{gpr ?? '—'}</div>
              <div className="text-xs text-gray-400">{gprDate ? `As of ${gprDate}` : geo?.regime}</div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">Joint stress</div>
              <div className="text-2xl font-bold text-white">{joint?.stress_score ?? '—'}</div>
              <div className="text-xs text-gray-400">{joint?.stress_regime ?? '—'}</div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">NIFTY 50</div>
              <div className="text-2xl font-bold text-white">{nifty ? formatPrice(nifty.price, nifty.currency) : '—'}</div>
              <div className="text-xs text-gray-400">{nifty ? `${nifty.change_pct >= 0 ? '+' : ''}${nifty.change_pct}%` : '—'}</div>
            </div>
            <div className="glass-card-inner p-4">
              <div className="text-xs text-gray-500 uppercase mb-1">USD/INR · Geo regime</div>
              <div className="text-2xl font-bold text-white">{usdInr ? formatPrice(usdInr.price, usdInr.currency) : geo?.regime ?? '—'}</div>
              <div className="text-xs text-gray-400">{vol?.available === false ? 'Vol model warming up' : vol?.regime ?? geo?.top_corridor ?? '—'}</div>
            </div>
          </div>
        </header>
      </Reveal>

      <Reveal>
        <section className="glass-card p-5">
          <h2 className="text-base font-semibold text-white mb-4">Historical Forsyt GPR Index</h2>
          <GprHistoryChart />
        </section>
      </Reveal>

      <Reveal>
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {[
            { label: 'Portfolio Risk Score', value: '64/100', demo: true },
            { label: 'Geo percentile', value: geo?.regime ?? '—', demo: false },
            { label: 'Vol regime', value: vol?.available === false ? 'N/A' : vol?.regime ?? '—', demo: false },
            { label: 'Top corridor', value: geo?.top_corridor ?? '—', demo: false },
          ].map((k) => (
            <div key={k.label} className="card-lift glass-card p-5">
              <div className="text-xs text-gray-500 uppercase mb-2">
                {k.label}{k.demo && ' · Demo'}
              </div>
              <div className="text-2xl text-white font-bold truncate">{k.value}</div>
            </div>
          ))}
        </section>
      </Reveal>

      <Reveal>
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="card-lift glass-card p-5 lg:col-span-4">
            <h2 className="text-base font-semibold text-white mb-4">Portfolio Allocation · Demo</h2>
            <p className="text-sm text-gray-400">Illustrative sector split — not connected to holdings API.</p>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between"><span>Tech</span><span>45%</span></div>
              <div className="flex justify-between"><span>Financials</span><span>25%</span></div>
              <div className="flex justify-between"><span>Energy</span><span>15%</span></div>
            </div>
          </div>
          <div className="card-lift glass-card p-5 lg:col-span-8">
            <h2 className="text-base font-semibold text-white mb-4">Scenario Analysis · Demo</h2>
            <p className="text-sm text-gray-400 mb-3">For live corridor risk see <Link to="/trade-corridor" className="text-primary underline">Trade &amp; Corridor Risk</Link>.</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-white/10">
                  <th className="pb-2 text-left">Scenario</th>
                  <th className="pb-2 text-right">Prob.</th>
                  <th className="pb-2">Impact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr><td className="py-2">Red Sea escalation</td><td className="text-right">35%</td><td className="text-[#ef4444]">Severe</td></tr>
                <tr><td className="py-2">Oil price shock</td><td className="text-right">20%</td><td className="text-[#f59e0b]">Moderate</td></tr>
                <tr><td className="py-2">USD-INR volatility</td><td className="text-right">65%</td><td className="text-[#f59e0b]">Moderate</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </Reveal>
    </div>
  )
}
