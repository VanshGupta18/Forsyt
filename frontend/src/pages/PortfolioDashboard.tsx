import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import Reveal from '../components/Reveal'
import GprHistoryChart from '../components/GprHistoryChart'
import ApiErrorBanner from '../components/ApiErrorBanner'
import MarketTicker from '../components/MarketTicker'
import {
  fetchPagePortfolio,
  formatCorridorName,
  formatPrice,
  orderMarketQuotes,
} from '../lib/api'
import {
  portfolioStressContext,
  sectorSensitivityByRegime,
  tiltClass,
  tiltLabel,
} from '../lib/portfolioCopy'
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

  const joint = dual?.joint_stress
  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility
  const nifty = quotes.find((q) => q.key === 'nifty')
  const usdInr = quotes.find((q) => q.key === 'usd_inr')

  const context = useMemo(
    () => portfolioStressContext(stressParam, corridorParam, geo?.regime),
    [stressParam, corridorParam, geo?.regime],
  )

  const sectors = useMemo(
    () => sectorSensitivityByRegime(geo?.regime, corridorParam ?? geo?.top_corridor),
    [geo?.regime, corridorParam, geo?.top_corridor],
  )

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
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
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
              <div className="text-xs text-gray-500 uppercase mb-1">USD/INR · Top route</div>
              <div className="text-2xl font-bold text-white truncate">
                {usdInr ? formatPrice(usdInr.price, usdInr.currency) : formatCorridorName(geo?.top_corridor) ?? '—'}
              </div>
              <div className="text-xs text-gray-400">
                {vol?.available === false ? 'Vol model warming up' : vol?.regime ?? geo?.top_corridor ?? '—'}
              </div>
            </div>
          </div>
        </header>
      </Reveal>

      <Reveal>
        <section className="glass-card p-5">
          <h2 className="text-base font-semibold text-white mb-2">Sector sensitivity · live regime</h2>
          <p className="text-sm text-gray-400 mb-4">
            Typical tilts when news risk is {geo?.regime?.toLowerCase() ?? 'unknown'} — not personalised to your holdings.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sectors.map((row) => (
              <div key={row.sector} className="bg-[#0d0d0d] p-4 border border-white/5">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <span className="text-sm text-white font-medium">{row.sector}</span>
                  <span className={`text-[10px] uppercase font-semibold shrink-0 ${tiltClass(row.tilt)}`}>
                    {tiltLabel(row.tilt)}
                  </span>
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">{row.note}</p>
              </div>
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
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="card-lift glass-card p-5 lg:col-span-4">
            <h2 className="text-base font-semibold text-white mb-4">Sample allocation · Demo</h2>
            <p className="text-sm text-gray-400">Connect holdings input when the exposure API ships — tilts above use live regime.</p>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between"><span>Tech</span><span>45%</span></div>
              <div className="flex justify-between"><span>Financials</span><span>25%</span></div>
              <div className="flex justify-between"><span>Energy</span><span>15%</span></div>
            </div>
          </div>
          <div className="card-lift glass-card p-5 lg:col-span-8">
            <h2 className="text-base font-semibold text-white mb-4">Scenario checklist · Demo</h2>
            <p className="text-sm text-gray-400 mb-3">
              For live route stress see{' '}
              <Link
                to={geo?.top_corridor ? `/trade-corridor?corridor=${encodeURIComponent(geo.top_corridor.toLowerCase())}` : '/trade-corridor'}
                className="text-primary underline"
              >
                Trade &amp; Corridor Risk
              </Link>
              .
            </p>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-white/10">
                  <th className="pb-2 text-left">Scenario</th>
                  <th className="pb-2 text-right">Signal</th>
                  <th className="pb-2">Typical tilt</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr>
                  <td className="py-2">{formatCorridorName(geo?.top_corridor) || 'Top corridor stress'}</td>
                  <td className="text-right">{geo?.regime ?? '—'}</td>
                  <td className="text-[#f59e0b]">Review imports</td>
                </tr>
                <tr>
                  <td className="py-2">Oil price shock</td>
                  <td className="text-right">{quotes.find((q) => q.key === 'brent')?.change_pct != null ? `${quotes.find((q) => q.key === 'brent')!.change_pct}%` : '—'}</td>
                  <td className="text-[#f59e0b]">Energy headwind</td>
                </tr>
                <tr>
                  <td className="py-2">USD-INR move</td>
                  <td className="text-right">{usdInr ? `${usdInr.change_pct >= 0 ? '+' : ''}${usdInr.change_pct}%` : '—'}</td>
                  <td className="text-[#f59e0b]">Mixed</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </Reveal>

      <p className="text-[10px] text-gray-500 text-center">
        Sector tilts are educational context from live GPR regime — not investment advice.
      </p>
    </div>
  )
}
