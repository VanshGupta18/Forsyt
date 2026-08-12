import { useCallback, useEffect, useMemo, useState } from 'react'
import Reveal from '../components/Reveal'
import ApiErrorBanner from '../components/ApiErrorBanner'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { corridorRiskLabel, fetchCorridors, formatCorridorName } from '../lib/api'
import LiveClock from '../components/LiveClock'

export default function TradeCorridorDashboard() {
  const [corridors, setCorridors] = useState<Awaited<ReturnType<typeof fetchCorridors>>['corridors']>([])
  const [asOf, setAsOf] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchCorridors()
      .then((payload) => {
        setCorridors(payload.corridors ?? [])
        setAsOf(typeof payload.date === 'string' ? payload.date : null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const sorted = useMemo(
    () => [...(corridors ?? [])].sort((a, b) => Number(b.corridor_risk ?? 0) - Number(a.corridor_risk ?? 0)),
    [corridors],
  )

  const highRiskCount = useMemo(
    () => sorted.filter((c) => Number(c.corridor_risk ?? 0) >= 50).length,
    [sorted],
  )

  const topAlerts = sorted.filter((c) => Number(c.corridor_risk ?? 0) > 0).slice(0, 3)
  const activeCorridors = sorted.filter((c) => Number(c.corridor_risk ?? 0) > 0 || Number(c.threat_index ?? 0) > 0)

  const stressSnapshot = useMemo(
    () =>
      sorted.slice(0, 5).map((row) => {
        const risk = Number(row.corridor_risk ?? 0)
        const threat = Number(row.threat_index ?? 0)
        const energy = Number(row.energy_risk ?? 0)
        const goods = Number(row.goods_risk ?? 0)
        const score = Math.max(risk, threat, energy, goods)
        return {
          key: row.corridor || row.corridor_name,
          name: formatCorridorName(row.corridor, row.corridor_name),
          score,
          energy,
          goods,
          label: corridorRiskLabel(score).label,
        }
      }),
    [sorted],
  )

  return (
    <div className="pb-stack-lg px-margin-page max-w-container-max mx-auto space-y-stack-lg">
      <Reveal className="space-y-2 pt-2">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <span className="eyebrow-badge">
              <span className="eyebrow-dot" />
              Live Corridor Monitoring
            </span>
            <h1 className="font-headline-lg text-headline-lg mb-2">Trade &amp; Corridor Risk Intelligence</h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant">
              Corridor scores from Forsyt news index{asOf ? ` · as of ${asOf}` : ''}.
            </p>
          </div>
          <button type="button" onClick={load} disabled={loading} className="text-xs px-3 py-1.5 rounded border border-white/20 hover:bg-white/5">
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </Reveal>

      {error && <ApiErrorBanner message={error} onRetry={load} />}

      {loading && !sorted.length && <LoadingSkeleton lines={5} />}

      <Reveal>
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter">
          <div className="card-lift glass-panel rounded-lg p-stack-md">
            <span className="font-label-md text-label-md text-on-surface-variant uppercase">Tracked corridors</span>
            <div className="font-display-lg text-display-lg">{loading ? '…' : sorted.length || '—'}</div>
          </div>
          <div className="card-lift glass-panel rounded-lg p-stack-md">
            <span className="font-label-md text-label-md text-error uppercase">High risk (≥50)</span>
            <div className="font-display-lg text-display-lg">{loading ? '…' : sorted.length ? highRiskCount : '—'}</div>
          </div>
          <div className="card-lift glass-panel rounded-lg p-stack-md">
            <span className="font-label-md text-label-md text-tertiary uppercase">With activity</span>
            <div className="font-display-lg text-display-lg">{loading ? '…' : activeCorridors.length}</div>
          </div>
          <div className="card-lift glass-panel rounded-lg p-stack-md">
            <span className="font-label-md text-label-md text-on-surface-variant uppercase">Snapshot date</span>
            <div className="font-display-lg text-display-lg text-base">{asOf ?? '—'}</div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
          <div className="lg:col-span-2 glass-panel rounded-lg p-stack-md">
            <h2 className="font-title-lg text-title-lg mb-4">Trade Route Status</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-body-md text-body-md">
                <thead>
                  <tr className="text-on-surface-variant border-b border-white/5">
                    <th className="pb-2 font-medium">Corridor</th>
                    <th className="pb-2 font-medium">Risk</th>
                    <th className="pb-2 font-medium">Threat</th>
                    <th className="pb-2 font-medium">Energy</th>
                    <th className="pb-2 font-medium">Goods</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {sorted.map((row) => {
                    const risk = Number(row.corridor_risk ?? 0)
                    const { label, className } = corridorRiskLabel(risk)
                    const displayName = formatCorridorName(row.corridor, row.corridor_name)
                    return (
                      <tr key={row.corridor || row.corridor_name}>
                        <td className="py-3 font-semibold">{displayName}</td>
                        <td className={`py-3 ${className}`}>{label} ({risk.toFixed(1)})</td>
                        <td className="py-3">{row.threat_index?.toFixed(1) ?? '—'}</td>
                        <td className="py-3">{row.energy_risk?.toFixed(1) ?? '—'}</td>
                        <td className="py-3">{row.goods_risk?.toFixed(1) ?? '—'}</td>
                      </tr>
                    )
                  })}
                  {!sorted.length && !error && !loading && (
                    <tr><td colSpan={5} className="py-4 text-on-surface-variant">No corridor data — run <code className="text-xs">python -m news_dataset.pipeline.daily_index</code>.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="glass-panel rounded-lg flex flex-col">
            <div className="p-stack-md border-b border-white/5 flex justify-between items-center">
              <h2 className="font-title-lg text-title-lg">Top corridor alerts</h2>
              <LiveClock />
            </div>
            <div className="p-stack-md flex-1 overflow-y-auto space-y-stack-md">
              {(topAlerts.length ? topAlerts : sorted.slice(0, 3)).map((row) => {
                const risk = Number(row.corridor_risk ?? 0)
                const severity = risk >= 50 ? 'text-error' : risk >= 20 ? 'text-tertiary' : 'text-secondary'
                const displayName = formatCorridorName(row.corridor, row.corridor_name)
                return (
                  <div key={row.corridor} className="bg-surface-container/50 border border-white/10 rounded-lg p-stack-sm">
                    <div className={`font-label-md text-label-md uppercase ${severity}`}>
                      {corridorRiskLabel(risk).label} · {risk.toFixed(1)}
                    </div>
                    <h3 className="font-body-lg font-semibold mt-1">{displayName}</h3>
                    <p className="text-sm text-on-surface-variant mt-1">
                      Threat {row.threat_index?.toFixed(1) ?? '—'} · Energy {row.energy_risk?.toFixed(1) ?? '—'} · Goods {row.goods_risk?.toFixed(1) ?? '—'}
                    </p>
                  </div>
                )
              })}
              {!sorted.length && !error && !loading && <p className="text-sm text-on-surface-variant">No alerts yet.</p>}
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="glass-panel rounded-lg p-stack-md">
          <h2 className="font-title-lg text-title-lg mb-2">Corridor stress snapshot</h2>
          <p className="text-sm text-on-surface-variant mb-4">
            Live energy and goods stress for top corridors from the Forsyt index{asOf ? ` (${asOf})` : ''}.
          </p>
          {!sorted.length && !loading && (
            <p className="text-sm text-on-surface-variant">No corridor data available yet.</p>
          )}
          <div className="space-y-5 max-w-2xl">
            {stressSnapshot.map((row) => (
              <div key={row.key}>
                <div className="flex justify-between text-sm mb-2 gap-2">
                  <span className="font-medium">{row.name}</span>
                  <span className="text-on-surface-variant shrink-0">
                    {row.label} · {row.score.toFixed(1)}
                  </span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                    <span className="w-14">Energy</span>
                    <div className="h-1.5 flex-1 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${row.energy >= 50 ? 'bg-error' : row.energy >= 20 ? 'bg-tertiary' : 'bg-secondary/70'}`}
                        style={{ width: `${Math.min(100, row.energy)}%` }}
                      />
                    </div>
                    <span className="w-10 text-right">{row.energy.toFixed(1)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                    <span className="w-14">Goods</span>
                    <div className="h-1.5 flex-1 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${row.goods >= 50 ? 'bg-error' : row.goods >= 20 ? 'bg-tertiary' : 'bg-secondary/70'}`}
                        style={{ width: `${Math.min(100, row.goods)}%` }}
                      />
                    </div>
                    <span className="w-10 text-right">{row.goods.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </Reveal>
    </div>
  )
}
