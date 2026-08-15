import { useCallback, useEffect, useState } from 'react'
import ApiErrorBanner from './ApiErrorBanner'
import PulseCard from './PulseCard'
import {
  corridorOperationalRisk,
  fetchCorridors,
  fetchGprCurrent,
  fetchHealth,
  fetchMarketQuotes,
  fetchPlatformStatus,
  formatCorridorName,
  formatPrice,
  orderMarketQuotes,
  type CorridorRow,
} from '../lib/api'
import { gprRegimeFromIndex, homeStatusLine } from '../lib/homeCopy'
import { geoRegimeClass, geoRegimeLabel } from '../lib/macroCopy'

export default function HomeLivePulse() {
  const [gprIndex, setGprIndex] = useState<number | null>(null)
  const [gprDate, setGprDate] = useState<string | null>(null)
  const [articles, setArticles] = useState<number | null>(null)
  const [niftyPrice, setNiftyPrice] = useState<string>('—')
  const [topCorridor, setTopCorridor] = useState<{ id: string; label: string; risk: number } | null>(null)
  const [pipelineRunAt, setPipelineRunAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)

    Promise.allSettled([
      fetchGprCurrent(),
      fetchHealth(),
      fetchMarketQuotes(['nifty']),
      fetchCorridors(),
      fetchPlatformStatus(),
    ])
      .then(([gprResult, healthResult, quotesResult, corridorsResult, statusResult]) => {
        const failures: string[] = []

        if (gprResult.status === 'fulfilled') {
          setGprIndex(gprResult.value.gpr_index ?? null)
          setGprDate(gprResult.value.date ?? null)
        } else {
          failures.push('GPR')
        }

        if (healthResult.status === 'fulfilled') {
          setArticles(healthResult.value.total_articles ?? null)
        } else {
          failures.push('health')
        }

        if (quotesResult.status === 'fulfilled') {
          const nifty = orderMarketQuotes(quotesResult.value.quotes ?? []).find((q) => q.key === 'nifty')
          setNiftyPrice(nifty ? formatPrice(nifty.price, nifty.currency) : '—')
        } else {
          failures.push('market')
        }

        if (corridorsResult.status === 'fulfilled') {
          let best: CorridorRow | null = null
          let bestRisk = -Infinity
          for (const row of corridorsResult.value.corridors ?? []) {
            const risk = corridorOperationalRisk(row)
            if (risk > bestRisk && row.corridor) {
              bestRisk = risk
              best = row
            }
          }
          if (best?.corridor) {
            setTopCorridor({
              id: best.corridor.toLowerCase(),
              label: formatCorridorName(best.corridor, best.corridor_name),
              risk: bestRisk,
            })
          }
        } else {
          failures.push('corridors')
        }

        if (statusResult.status === 'fulfilled') {
          setPipelineRunAt(statusResult.value.last_pipeline_runs?.platform_refresh?.run_at ?? null)
        }

        if (failures.length === 4) {
          setError('Live data unavailable — check that the API server is running.')
        } else if (failures.length > 0) {
          setError(`Some live data could not be loaded (${failures.join(', ')}).`)
        }
      })
      .catch(() => setError('Live data unavailable — check that the API server is running.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const regime = gprRegimeFromIndex(gprIndex)
  const regimeLabel = geoRegimeLabel(regime)
  const regimeClass = geoRegimeClass(regime)
  const corridorHref = topCorridor
    ? `/trade-corridor?corridor=${encodeURIComponent(topCorridor.id)}`
    : '/trade-corridor'

  return (
    <div className="space-y-3 pt-6 border-t border-white/10">
      <p className="text-[11px] text-corridor-muted/80">{homeStatusLine(gprDate, pipelineRunAt)}</p>
      <div className="home-pulse-track flex gap-2 pb-1">
        <PulseCard
          label="News risk"
          value={loading ? '…' : gprIndex != null ? String(Math.round(gprIndex)) : '—'}
          valueClass="text-corridor-watch"
          href="/news"
        />
        <PulseCard
          label="Regime"
          value={loading ? '…' : regimeLabel}
          valueClass={regimeClass}
        />
        <PulseCard
          label="Top corridor"
          value={loading ? '…' : topCorridor?.label ?? '—'}
          valueClass="text-corridor-alert"
          href={corridorHref}
        />
        <PulseCard
          label="NIFTY 50"
          value={loading ? '…' : niftyPrice}
          href="/macroeconomics"
        />
        <PulseCard
          label="Articles indexed"
          value={loading ? '…' : articles != null ? String(articles) : '—'}
        />
      </div>
      {error && <ApiErrorBanner message={error} onRetry={load} />}
    </div>
  )
}
