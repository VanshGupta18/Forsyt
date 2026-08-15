import { useCallback, useEffect, useState } from 'react'
import Reveal from '../components/Reveal'
import ApiErrorBanner from '../components/ApiErrorBanner'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { fetchAccuracyMetrics, fetchDualSignal, type AccuracyMetricsPayload, type DualSignalPayload } from '../lib/api'

function MetricCard({
  label,
  value,
  sub,
  pass,
}: {
  label: string
  value: string
  sub?: string
  pass?: boolean | null
}) {
  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col gap-1 min-w-[140px]">
      <span className="text-xs text-gray-400 uppercase tracking-wide">{label}</span>
      <span className={`text-2xl font-bold ${pass === true ? 'text-[#10B981]' : pass === false ? 'text-[#EF4444]' : 'text-white'}`}>
        {value}
      </span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  )
}

function PassBadge({ pass }: { pass?: boolean | null }) {
  if (pass == null) return null
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded font-medium ${
        pass ? 'bg-[#10B981]/15 text-[#10B981]' : 'bg-[#EF4444]/15 text-[#EF4444]'
      }`}
    >
      {pass ? 'PASS' : 'FAIL'}
    </span>
  )
}

export default function AccuracyDashboard() {
  const [data, setData] = useState<AccuracyMetricsPayload | null>(null)
  const [dual, setDual] = useState<DualSignalPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshingVol, setRefreshingVol] = useState(false)

  const load = useCallback((refreshVol = false) => {
    if (refreshVol) setRefreshingVol(true)
    else setLoading(true)
    setError(null)
    fetchAccuracyMetrics(refreshVol)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => {
        setLoading(false)
        setRefreshingVol(false)
      })
  }, [])

  useEffect(() => {
    load(false)
    fetchDualSignal(false)
      .then(setDual)
      .catch(() => undefined)
  }, [load])

  const drivingMeta = dual?.driving_events_meta

  const ing = data?.ingestion
  const nlp = data?.nlp
  const gpr = data?.gpr_index
  const corridors = data?.corridors
  const vol = data?.nifty_volatility

  return (
    <div className="flex-grow max-w-[1600px] mx-auto w-full px-6 py-8 flex flex-col gap-8">
      <Reveal>
        <section className="space-y-3">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            Platform Quality
          </span>
          <h1 className="text-4xl font-bold text-white">Accuracy & Validation Metrics</h1>
          <p className="text-gray-400 max-w-3xl">
            Live pipeline health plus offline benchmarks for news ingestion, NLP tagging, GPR index, trade corridors, and NIFTY volatility models.
          </p>
          {data?.generated_at && (
            <p className="text-xs text-gray-500">Generated {new Date(data.generated_at).toLocaleString()}</p>
          )}
        </section>
      </Reveal>

      {error && <ApiErrorBanner message={error} onRetry={() => load(false)} />}
      {loading && !data && <LoadingSkeleton lines={4} />}

      {data && (
        <>
          <Reveal>
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-lg">rss_feed</span>
                News Ingestion
              </h2>
              <p className="text-sm text-gray-500">{ing?.description}</p>
              <div className="flex flex-wrap gap-4">
                <MetricCard label="Total articles" value={String(ing?.total_articles ?? '—')} />
                <MetricCard label="Geo-tier articles" value={String(ing?.tier_articles ?? '—')} />
                <MetricCard
                  label="7d ingest yield"
                  value={ing?.ingest_yield_7d_pct != null ? `${ing.ingest_yield_7d_pct}%` : '—'}
                  sub={ing?.fetched_7d ? `${ing.ingested_7d}/${ing.fetched_7d} articles` : undefined}
                />
                <MetricCard
                  label="Sources healthy"
                  value={ing?.sources_total ? `${ing.sources_healthy}/${ing.sources_total}` : '—'}
                  sub={ing?.sources_unhealthy ? `${ing.sources_unhealthy} failing` : 'All OK'}
                  pass={ing?.sources_unhealthy === 0 ? true : ing?.sources_unhealthy ? false : null}
                />
                <MetricCard
                  label="GPR index days"
                  value={String(ing?.gpr_index_days ?? '—')}
                  sub={ing?.gpr_latest_date ? `Latest: ${ing.gpr_latest_date}` : undefined}
                />
              </div>
              {ing?.feed_health && Object.keys(ing.feed_health).length > 0 && (
                <div className="glass-panel rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="text-gray-400 border-b border-white/10">
                      <tr>
                        <th className="text-left p-3 font-medium">Source</th>
                        <th className="text-left p-3 font-medium">Failures</th>
                        <th className="text-left p-3 font-medium">Last success</th>
                        <th className="text-left p-3 font-medium">Last error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(ing.feed_health).map(([name, h]) => (
                        <tr key={name} className="border-b border-white/5">
                          <td className="p-3 text-white">{name}</td>
                          <td className={`p-3 ${(h.consecutive_failures ?? 0) > 0 ? 'text-[#EF4444]' : 'text-[#10B981]'}`}>
                            {h.consecutive_failures ?? 0}
                          </td>
                          <td className="p-3 text-gray-400">{h.last_success ? new Date(h.last_success).toLocaleString() : '—'}</td>
                          <td className="p-3 text-gray-500 truncate max-w-xs">{h.last_error ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </Reveal>

          <Reveal>
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-lg">label</span>
                NLP Tagging
              </h2>
              <p className="text-sm text-gray-500">{nlp?.description}</p>
              <div className="flex flex-wrap gap-4">
                <MetricCard
                  label="NLP coverage"
                  value={nlp?.coverage_pct != null ? `${nlp.coverage_pct}%` : '—'}
                  sub={`${nlp?.nlp_complete ?? 0} / ${nlp?.tier_articles ?? 0} tier articles`}
                  pass={nlp?.coverage_pct != null ? nlp.coverage_pct >= 95 : null}
                />
                <MetricCard label="Pending NLP" value={String(nlp?.nlp_pending ?? '—')} />
                <MetricCard
                  label="Corridor fixtures"
                  value={
                    nlp?.corridor_tagging?.pass_rate_pct != null
                      ? `${nlp.corridor_tagging.pass_rate_pct}%`
                      : '—'
                  }
                  sub={
                    nlp?.corridor_tagging
                      ? `${nlp.corridor_tagging.passed}/${nlp.corridor_tagging.total} labelled cases`
                      : undefined
                  }
                  pass={
                    nlp?.corridor_tagging?.pass_rate_pct != null
                      ? nlp.corridor_tagging.pass_rate_pct === 100
                      : null
                  }
                />
              </div>
              {nlp?.corridor_tagging?.cases && (
                <div className="flex flex-wrap gap-2">
                  {nlp.corridor_tagging.cases.map((c) => (
                    <span
                      key={c.label}
                      className={`text-xs px-2 py-1 rounded border ${
                        c.pass ? 'border-[#10B981]/30 text-[#10B981]' : 'border-[#EF4444]/30 text-[#EF4444]'
                      }`}
                    >
                      {c.label}
                    </span>
                  ))}
                </div>
              )}
            </section>
          </Reveal>

          <Reveal>
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-lg">show_chart</span>
                GPR Index Benchmark
              </h2>
              <p className="text-sm text-gray-500">{gpr?.description}</p>
              <div className="flex flex-wrap gap-4 items-start">
                <MetricCard
                  label="Caldara MA30 r"
                  value={gpr?.caldara_ma30_r != null ? String(gpr.caldara_ma30_r) : '—'}
                  sub={`Target ${gpr?.target_r ?? 0.5}`}
                  pass={gpr?.caldara_ma30_pass}
                />
              </div>
              {gpr?.benchmarks && (
                <div className="glass-panel rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="text-gray-400 border-b border-white/10">
                      <tr>
                        <th className="text-left p-3">Comparison</th>
                        <th className="text-left p-3">Pearson r</th>
                        <th className="text-left p-3">Days</th>
                        <th className="text-left p-3">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gpr.benchmarks.map((b) => (
                        <tr key={b.comparison} className="border-b border-white/5">
                          <td className="p-3 text-white">{b.comparison}</td>
                          <td className="p-3">{b.pearson_r ?? '—'}</td>
                          <td className="p-3 text-gray-400">{b.days_overlap}</td>
                          <td className="p-3">
                            <PassBadge pass={b.pass} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </Reveal>

          <Reveal>
            <section className="space-y-4">
              <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-lg">route</span>
                Trade Corridors
              </h2>
              <p className="text-sm text-gray-500">{corridors?.description}</p>
              <div className="flex flex-wrap gap-4">
                <MetricCard
                  label="Parent leakage check"
                  value={
                    corridors?.parent_leakage_pass_rate_pct != null
                      ? `${corridors.parent_leakage_pass_rate_pct}%`
                      : '—'
                  }
                  sub={`${corridors?.parent_leakage_passed}/${corridors?.corridors_validated} corridors`}
                  pass={
                    corridors?.parent_leakage_pass_rate_pct != null
                      ? corridors.parent_leakage_pass_rate_pct === 100
                      : null
                  }
                />
              </div>
              {corridors?.corridors && corridors.corridors.length > 0 && (
                <div className="glass-panel rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="text-gray-400 border-b border-white/10">
                      <tr>
                        <th className="text-left p-3">Corridor</th>
                        <th className="text-left p-3">Parent correlation</th>
                        <th className="text-left p-3">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {corridors.corridors.map((c) => (
                        <tr key={c.corridor} className="border-b border-white/5">
                          <td className="p-3 text-white">{c.corridor}</td>
                          <td className="p-3">{c.parent_correlation}</td>
                          <td className="p-3">
                            <PassBadge pass={c.pass} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </Reveal>

          <Reveal>
            <section className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-lg">candlestick_chart</span>
                    NIFTY Volatility Model
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">{vol?.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => load(true)}
                  disabled={refreshingVol}
                  className="text-xs px-3 py-1.5 rounded border border-white/20 hover:bg-white/5 disabled:opacity-50"
                >
                  {refreshingVol ? 'Running backtest…' : 'Recompute vol backtest'}
                </button>
              </div>
              <div className="flex flex-wrap gap-4">
                <MetricCard
                  label="Market-only ROC-AUC"
                  value={vol?.market_only_roc_auc != null ? String(vol.market_only_roc_auc) : '—'}
                  sub={`${vol?.horizon_days ?? 5}d HIGH_VOL horizon`}
                />
                <MetricCard
                  label="Market + GPR ROC-AUC"
                  value={vol?.market_plus_gpr_roc_auc != null ? String(vol.market_plus_gpr_roc_auc) : '—'}
                />
                <MetricCard
                  label="GPR incremental AUC"
                  value={
                    vol?.gpr_incremental_roc_auc != null
                      ? `${vol.gpr_incremental_roc_auc > 0 ? '+' : ''}${vol.gpr_incremental_roc_auc}`
                      : '—'
                  }
                  sub={vol?.note}
                  pass={vol?.gpr_incremental_roc_auc != null ? vol.gpr_incremental_roc_auc > 0 : null}
                />
              </div>
              {vol?.source && (
                <p className="text-xs text-gray-500">Source: {vol.source.replace(/_/g, ' ')}</p>
              )}
            </section>
          </Reveal>

          {drivingMeta && (
            <Reveal>
              <section className="glass-panel rounded-xl p-6 space-y-4">
                <h2 className="text-lg font-semibold text-white">Stress monitor driving headlines</h2>
                <p className="text-sm text-gray-500">Filter QA from latest dual-signal payload</p>
                <div className="flex flex-wrap gap-4">
                  <MetricCard label="Candidates scanned" value={String(drivingMeta.candidates_scanned ?? '—')} />
                  <MetricCard label="Geo + market pass" value={String(drivingMeta.geo_market_pass ?? '—')} />
                  <MetricCard label="Geo-only fallback" value={String(drivingMeta.geo_only_pass ?? '—')} />
                  <MetricCard label="Returned" value={String(drivingMeta.returned ?? '—')} />
                  <MetricCard
                    label="Gate B relaxed"
                    value={drivingMeta.gate_b_relaxed ? 'Yes' : 'No'}
                    pass={drivingMeta.gate_b_relaxed ? false : true}
                  />
                </div>
              </section>
            </Reveal>
          )}

          {data.disclaimer && (
            <p className="text-xs text-gray-600 border-t border-white/5 pt-6">{data.disclaimer}</p>
          )}
        </>
      )}
    </div>
  )
}
