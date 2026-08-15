import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ApiErrorBanner from '../components/ApiErrorBanner'
import LoadingSkeleton from '../components/LoadingSkeleton'
import CorridorRiskMap from '../components/CorridorRiskMap'
import CorridorRouteList from '../components/CorridorRouteList'
import CorridorNewsTicker from '../components/CorridorNewsTicker'
import ScoreBar from '../components/ScoreBar'
import {
  corridorOperationalRisk,
  corridorRiskLabel,
  fetchCorridors,
  fetchEventsFeed,
  fetchPlatformStatus,
  formatCorridorName,
  type CargoFocus,
  type CorridorCategory,
  type CorridorsPayload,
  type NewsArticle,
} from '../lib/api'
import { CORRIDOR_CATEGORIES, CORRIDOR_SEARCH_TERMS } from '../lib/corridorGeo'
import {
  businessActionLabel,
  businessTierClass,
  businessTierLabel,
  calibratingBadge,
  CORRIDOR_EYEBROW,
  CORRIDOR_HEADLINES_TITLE,
  corridorStatusLine,
  CORRIDOR_PAGE_DISCLAIMER,
  CORRIDOR_PAGE_SUBTITLE,
  displayStressScore,
  newsMentionsLine,
  OPERATIONAL_SCORE_NOTE,
  SCORE_LABELS,
  spikeBadge,
  spikeBadgeDetail,
  tierAccentColor,
  watchlistAlertLine,
} from '../lib/corridorCopy'
import {
  CONTINGENCY_CHECKLIST,
  CORRIDOR_ALTERNATIVES,
  suggestCorridors,
  type RouteMode,
} from '../lib/corridorRoutes'
import { isWatchlisted, loadWatchlist, toggleWatchlist } from '../lib/corridorWatchlist'

const ADVISORY: Record<string, string> = {
  High: 'Elevated geopolitical activity near this route. Review contingency routing and insurance cover before committing new shipments.',
  Medium: 'Some risk signals present. Worth monitoring before scheduling time-sensitive cargo through this route.',
  Low: 'No elevated concerns detected right now. Standard routing conditions apply.',
}

function tierDotClass(risk: number): string {
  return businessTierClass(risk).replace('text-', 'bg-')
}

const CORRIDOR_POLL_MS = 15 * 60 * 1000

export default function CorridorRiskDashboard() {
  const [searchParams] = useSearchParams()
  const corridorParam = searchParams.get('corridor')?.toLowerCase() ?? null
  const [payload, setPayload] = useState<CorridorsPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<string | null>(null)
  const [headlines, setHeadlines] = useState<NewsArticle[]>([])
  const [headlinesLoading, setHeadlinesLoading] = useState(false)
  const [category, setCategory] = useState<'all' | CorridorCategory>('all')
  const [cargoFocus, setCargoFocus] = useState<CargoFocus>('both')
  const [watchlist, setWatchlist] = useState<string[]>(() => loadWatchlist())
  const [watchlistOnly, setWatchlistOnly] = useState(() => loadWatchlist().length > 0)
  const [routeOrigin, setRouteOrigin] = useState('')
  const [routeDestination, setRouteDestination] = useState('')
  const [routeMode, setRouteMode] = useState<RouteMode>('sea')
  const [finderOpen, setFinderOpen] = useState(false)
  const [pipelineRunAt, setPipelineRunAt] = useState<string | null>(null)

  const corridors = payload?.corridors ?? []
  const asOf = payload?.date ?? null

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchCorridors()
      .then(setPayload)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const refreshStatus = () => {
      fetchPlatformStatus()
        .then((status) => {
          setPipelineRunAt(status.last_pipeline_runs?.platform_refresh?.run_at ?? null)
        })
        .catch(() => undefined)
    }
    refreshStatus()
    const id = window.setInterval(refreshStatus, CORRIDOR_POLL_MS)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    const id = window.setInterval(() => {
      fetchCorridors()
        .then(setPayload)
        .catch(() => undefined)
    }, CORRIDOR_POLL_MS)
    return () => window.clearInterval(id)
  }, [])

  const filtered = useMemo(() => {
    let rows = [...corridors]
    if (category !== 'all') {
      rows = rows.filter((row) => {
        const key = row.corridor?.toLowerCase() ?? ''
        const cat = row.category ?? CORRIDOR_CATEGORIES[key] ?? 'sea'
        return cat === category
      })
    }
    if (watchlistOnly && watchlist.length) {
      rows = rows.filter((row) => watchlist.includes(row.corridor?.toLowerCase() ?? ''))
    }
    return rows.sort((a, b) => corridorOperationalRisk(b) - corridorOperationalRisk(a))
  }, [corridors, category, watchlistOnly, watchlist])

  useEffect(() => {
    if (!corridorParam || !corridors.length) return
    const match = corridors.find((c) => c.corridor?.toLowerCase() === corridorParam)
    if (match?.corridor) {
      setSelected(match.corridor.toLowerCase())
    }
  }, [corridorParam, corridors])

  useEffect(() => {
    if (!selected && filtered.length) {
      setSelected(filtered[0].corridor?.toLowerCase() ?? null)
    }
  }, [filtered, selected])

  useEffect(() => {
    if (!selected) return
    const term = CORRIDOR_SEARCH_TERMS[selected] ?? formatCorridorName(selected)

    const refreshHeadlines = () => {
      setHeadlinesLoading(true)
      fetchEventsFeed({ corridor: term, limit: 8 })
        .then((res) => setHeadlines(res.events ?? []))
        .catch(() => setHeadlines([]))
        .finally(() => setHeadlinesLoading(false))
    }

    refreshHeadlines()
    const id = window.setInterval(refreshHeadlines, CORRIDOR_POLL_MS)
    return () => window.clearInterval(id)
  }, [selected])

  const selectedRow =
    filtered.find((c) => c.corridor?.toLowerCase() === selected) ??
    corridors.find((c) => c.corridor?.toLowerCase() === selected) ??
    null
  const operational = corridorOperationalRisk(selectedRow ?? {})
  const { label: tierLabel } = corridorRiskLabel(operational)
  const threat = Number(selectedRow?.threat_index ?? 0)
  const energy = Number(selectedRow?.energy_risk ?? 0)
  const goods = Number(selectedRow?.goods_risk ?? 0)
  const energyExposure = Number(selectedRow?.energy_exposure ?? 0)
  const goodsExposure = Number(selectedRow?.goods_exposure ?? 0)
  const hitCount = Number(selectedRow?.corridor_hit_count ?? 0)
  const isCalibrating = selectedRow?.score_status === 'insufficient_history'
  const dailyRisk = Number(selectedRow?.corridor_risk ?? 0)
  const spikeToday = hitCount > 0 && dailyRisk > operational + 5
  const highWatchlist = corridors.filter(
    (row) => watchlist.includes(row.corridor?.toLowerCase() ?? '') && corridorOperationalRisk(row) >= 50,
  )

  const routeSuggestions = useMemo(
    () => suggestCorridors(routeOrigin, routeDestination, routeMode),
    [routeOrigin, routeDestination, routeMode],
  )

  const handleWatchlistToggle = (id: string) => {
    const next = toggleWatchlist(id)
    setWatchlist(next)
    if (!next.length) setWatchlistOnly(false)
  }

  const applyRouteFinder = () => {
    if (!routeSuggestions.length) return
    setSelected(routeSuggestions[0])
    setCategory('all')
    setWatchlistOnly(false)
    setFinderOpen(false)
  }

  const listRows = filtered.length ? filtered : corridors

  return (
    <div className="corridor-page pb-10 px-margin-page max-w-container-max mx-auto space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
        <div className="space-y-2 max-w-2xl">
          <span
            className="eyebrow-badge"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.85)' }}
          >
            <span className="eyebrow-dot" style={{ background: '#ffffff', boxShadow: '0 0 8px 2px rgba(255,255,255,0.25)' }} />
            {CORRIDOR_EYEBROW}
          </span>
          <h1 className="corridor-display font-headline-lg text-headline-lg">Is your trade route at risk?</h1>
          <p className="font-body-lg text-body-lg text-corridor-muted">{CORRIDOR_PAGE_SUBTITLE}</p>
          <p className="text-xs text-corridor-muted/80 max-w-xl">{CORRIDOR_PAGE_DISCLAIMER}</p>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <button type="button" onClick={load} disabled={loading} className="corridor-btn text-xs px-3 py-1.5">
            {loading ? 'Loading…' : 'Refresh'}
          </button>
          <span className="font-label-md text-[11px] text-corridor-muted/70">
            {corridorStatusLine(asOf, pipelineRunAt)}
            {payload?.stale_warning ? ` · ${payload.stale_warning}` : ''}
          </span>
        </div>
      </header>

      {highWatchlist.length > 0 && (
        <div className="corridor-alert-banner px-4 py-2.5 text-sm font-semibold">{watchlistAlertLine(highWatchlist.length)}</div>
      )}

      {error && <ApiErrorBanner message={error} onRetry={load} />}

      {/* Toolbar: filters + optional route finder toggle */}
      <div className="flex flex-wrap items-center gap-2 mt-2">
        {(['all', 'sea', 'land', 'strategic'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            data-active={category === tab}
            onClick={() => setCategory(tab)}
            className="corridor-tab px-2.5 py-1.5"
          >
            {tab === 'all' ? 'All' : tab === 'sea' ? 'Sea' : tab === 'land' ? 'Land' : 'Strategic'}
          </button>
        ))}
        <span className="w-px h-3.5 bg-white/10" />
        {(['both', 'goods', 'energy'] as CargoFocus[]).map((focus) => (
          <button
            key={focus}
            type="button"
            data-active={cargoFocus === focus}
            onClick={() => setCargoFocus(focus)}
            className="corridor-tab px-2.5 py-1.5"
          >
            {focus === 'both' ? 'All cargo' : focus === 'goods' ? 'Goods' : 'Energy'}
          </button>
        ))}
        {watchlist.length > 0 && (
          <>
            <span className="w-px h-3.5 bg-white/10" />
            <button
              type="button"
              data-active={watchlistOnly}
              onClick={() => setWatchlistOnly((v) => !v)}
              className="corridor-tab px-2.5 py-1.5"
            >
              My routes ({watchlist.length})
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => setFinderOpen((v) => !v)}
          className="corridor-tab px-2.5 py-1.5 ml-auto"
          data-active={finderOpen}
        >
          {finderOpen ? 'Hide finder' : 'Find a route'}
        </button>
      </div>

      {finderOpen && (
        <div className="corridor-panel p-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          <input
            value={routeOrigin}
            onChange={(e) => setRouteOrigin(e.target.value)}
            placeholder="Origin (e.g. Mumbai)"
            className="corridor-input px-3 py-2 text-sm"
          />
          <input
            value={routeDestination}
            onChange={(e) => setRouteDestination(e.target.value)}
            placeholder="Destination (e.g. Rotterdam)"
            className="corridor-input px-3 py-2 text-sm"
          />
          <select
            value={routeMode}
            onChange={(e) => setRouteMode(e.target.value as RouteMode)}
            className="corridor-input px-3 py-2 text-sm"
          >
            <option value="sea">Sea freight</option>
            <option value="road">Road border</option>
            <option value="rail">Rail border</option>
          </select>
          <button type="button" onClick={applyRouteFinder} className="corridor-btn px-3 py-2 text-sm font-semibold">
            Show routes
          </button>
          {routeSuggestions.length > 0 && (routeOrigin || routeDestination) && (
            <p className="sm:col-span-2 lg:col-span-4 text-xs text-corridor-muted">
              Suggested: {routeSuggestions.map((id) => formatCorridorName(id)).join(' · ')}
            </p>
          )}
        </div>
      )}

      {loading && !filtered.length && <LoadingSkeleton lines={5} />}

      {/* Map + detail — visible immediately, no Reveal delay */}
      <section className="grid grid-cols-1 md:grid-cols-[1.45fr_1fr] gap-4 items-start">
        <div className="corridor-panel p-3 min-w-0">
          <CorridorRiskMap
            corridors={listRows}
            selected={selected}
            category={category}
            onSelect={setSelected}
          />
          <CorridorRouteList
            rows={listRows}
            selected={selected}
            onSelect={setSelected}
            onToggleWatchlist={handleWatchlistToggle}
          />
        </div>

        <div className="corridor-panel p-4 flex flex-col md:sticky md:top-24 md:max-h-[calc(100vh-7rem)] md:overflow-y-auto">
          {selectedRow ? (
            <>
              <div>
                <span className="corridor-kicker block mb-1">Selected route</span>
                <div className="flex items-baseline gap-3">
                  <span
                    className="corridor-score text-4xl leading-none shrink-0"
                    style={{ color: tierAccentColor(operational) }}
                    title={OPERATIONAL_SCORE_NOTE}
                  >
                    {displayStressScore(selectedRow)}
                  </span>
                  <div>
                    <h3 className="corridor-display text-lg leading-snug">
                      {formatCorridorName(selectedRow.corridor, selectedRow.corridor_name)}
                    </h3>
                    <p className="text-[10px] text-corridor-muted/70 mt-0.5">{OPERATIONAL_SCORE_NOTE}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold bg-[#111111] ${businessTierClass(operational)}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${tierDotClass(operational)}`} />
                    {businessActionLabel(selectedRow.action_label)}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-[#111111] text-corridor-muted">
                    Stress: {businessTierLabel(operational)}
                  </span>
                  {isCalibrating && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-corridor-watch/10 text-corridor-watch">
                      {calibratingBadge()}
                    </span>
                  )}
                  {spikeToday && !isCalibrating && (
                    <span
                      className="text-xs px-2 py-0.5 rounded-full bg-corridor-alert/10 text-corridor-alert"
                      title={spikeBadgeDetail()}
                    >
                      {spikeBadge()}
                    </span>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={() => selected && handleWatchlistToggle(selected)}
                className="mt-2 text-xs text-corridor-muted underline hover:text-white text-left"
              >
                {selected && isWatchlisted(selected) ? 'Remove from my routes' : 'Pin to my routes'}
              </button>

              <p
                className="text-sm text-corridor-muted mt-3 p-3 rounded-sm corridor-advisory border-l-2"
                style={{ borderLeftColor: tierAccentColor(operational) }}
              >
                {ADVISORY[tierLabel]}
              </p>

              <p className="text-xs text-corridor-muted mt-2">{newsMentionsLine(hitCount)}</p>

              <div className="space-y-2 mt-3">
                <ScoreBar label={SCORE_LABELS.threat} value={threat} />
                {(cargoFocus === 'both' || cargoFocus === 'goods') && goodsExposure > 0 && (
                  <ScoreBar label={SCORE_LABELS.goods} value={goods} />
                )}
                {(cargoFocus === 'both' || cargoFocus === 'energy') && energyExposure > 0 && (
                  <ScoreBar label={SCORE_LABELS.energy} value={energy} />
                )}
              </div>

              {selected && CORRIDOR_ALTERNATIVES[selected] && operational >= 20 && (
                <div className="mt-3 p-3 rounded-sm bg-[#0d0d0d] text-sm text-corridor-muted">
                  <strong className="text-[var(--corridor-text)] block mb-1">Alternative routing</strong>
                  {CORRIDOR_ALTERNATIVES[selected]}
                </div>
              )}

              <div className="mt-3 p-3 rounded-sm bg-[#0d0d0d]">
                <strong className="text-sm text-[var(--corridor-text)] block mb-2">Contingency checklist</strong>
                <ul className="text-xs text-corridor-muted space-y-1 list-disc pl-4">
                  {(CONTINGENCY_CHECKLIST[tierLabel] ?? CONTINGENCY_CHECKLIST.Low).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </>
          ) : (
            <p className="text-sm text-corridor-muted">Select a route on the map or strip below.</p>
          )}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold">{CORRIDOR_HEADLINES_TITLE}</h2>
          {selected && (
            <Link
              to={`/news?corridor=${encodeURIComponent(CORRIDOR_SEARCH_TERMS[selected] ?? selected)}`}
              className="text-xs text-corridor-muted underline hover:text-white"
            >
              View all news
            </Link>
          )}
        </div>
        <CorridorNewsTicker articles={headlines} loading={headlinesLoading} />
      </section>
    </div>
  )
}
