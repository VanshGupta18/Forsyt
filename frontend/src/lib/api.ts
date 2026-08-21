// ---------------------------------------------------------------------------
// This file is the app's DATA LAYER: every network request the frontend
// makes to the backend API goes through the `fetchJSON` helper below, and
// every function exported from this file wraps one specific API endpoint.
// Pages and components never call `fetch()` directly — they import one of
// the `fetch...` functions from here instead. That keeps "how do I talk to
// the backend" in one place, and gives every response a TypeScript type (see
// the `export type ...` blocks further down) so mistakes like typo'd field
// names get caught while you're writing code, not at runtime.
//
// `API_BASE` is either empty (local dev — see vite.config.ts's proxy, which
// forwards "/api" and "/health" straight to the Python backend) or a full
// URL like "https://api.example.com" (production — set via the VITE_API_BASE
// environment variable in frontend/.env). Every request below is built as
// `${API_BASE}${path}`, so in dev it's just a relative path like "/health".
// ---------------------------------------------------------------------------
const API_BASE = String(import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

// Shared fetch wrapper used by every function below. `<T>` is a TypeScript
// "generic" — it lets each caller say "I expect the JSON back to look like
// type X", e.g. `fetchJSON<HealthPayload>('/health')`. This function itself
// doesn't validate the shape of the response (the backend is trusted to
// return what it promises); it just does the actual `fetch()` call, throws a
// helpful Error if the HTTP status isn't ok (2xx), and parses the body as JSON.
export async function fetchJSON<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url)
  if (!res.ok) {
    const hint =
      res.status === 403 && API_BASE
        ? ' — check VITE_API_BASE in frontend/.env (use empty string for local dev)'
        : ''
    throw new Error(`${url} -> ${res.status}${hint}`)
  }
  return res.json() as Promise<T>
}

export type GprCurrent = {
  date?: string
  gpr_index?: number
  gpr_7ma?: number
  gpr_30ma?: number
  total_articles?: number
  data_source?: 'postgres' | 'csv'
  updated_at?: string
  refresh_interval_minutes?: number
  stale_warning?: string | null
}

export type GprHistoryPoint = {
  date: string
  gpr_index?: number
  gpr_7ma?: number
  gpr_30ma?: number
}

export type GprHistoryPayload = {
  history?: GprHistoryPoint[]
}

export type HealthPayload = {
  total_articles?: number
  status?: string
  gpr_latest_date?: string | null
  corridor_latest_date?: string | null
  news_latest_at?: string | null
  last_platform_refresh?: {
    run_at?: string
    status?: string
    details?: Record<string, unknown>
  } | null
  stale_warning?: string | null
}

export type PlatformStatusPayload = {
  database_configured?: boolean
  allow_csv_fallback?: boolean
  refresh_interval_minutes?: number
  latest_dates?: {
    corridor?: string | null
    gpr?: string | null
    news?: string | null
    dual_signal?: string | null
  }
  data_sources?: Record<string, string | null | undefined>
  updated_at?: Record<string, string | null | undefined>
  last_pipeline_runs?: Record<string, {
    run_at?: string
    status?: string
    details?: Record<string, unknown>
  } | null | undefined>
  stale_warning?: string | null
  news_total_articles?: number
}

export type PlatformStatusSlim = Pick<
  PlatformStatusPayload,
  'refresh_interval_minutes' | 'latest_dates' | 'stale_warning' | 'last_pipeline_runs'
>

export type MarketHistoriesBatch = {
  histories: Record<string, MarketHistoryPayload>
  errors?: string[]
}

export type HomePageBundle = {
  health: HealthPayload
  gpr_current: GprCurrent | null
  corridors: CorridorsPayload
  quotes: MarketQuotesPayload
  dual_signal: DualSignalPayload | null
  status: PlatformStatusSlim
}

export type MacroPageBundle = {
  dual_signal: DualSignalPayload | null
  quotes: MarketQuotesPayload
  indicators: MarketIndicatorsPayload
  gpr_current: GprCurrent | null
  gpr_history: GprHistoryPayload
  corridors: CorridorsPayload
  market_histories: MarketHistoriesBatch
  status: PlatformStatusSlim
}

export type NewsPageBundle = {
  events: NewsArticle[]
  gpr_current: GprCurrent | null
  gpr_history: GprHistoryPayload
  status: PlatformStatusSlim
}

export type CorridorPageBundle = {
  corridors: CorridorsPayload
  status: PlatformStatusSlim
  events: NewsArticle[]
  selected_corridor: string | null
}

export type PortfolioPageBundle = {
  gpr_current: GprCurrent | null
  dual_signal: DualSignalPayload | null
  quotes: MarketQuotesPayload
  gpr_history: GprHistoryPayload
}

export type NewsArticle = {
  title?: string
  link?: string
  source?: string
  tier?: number
  published_at?: string
  scraped_at?: string
  nlp_themes?: string
  image_url?: string | null
  why_included?: 'geo_theme' | 'market_keyword' | 'corridor_match'
}

export type MarketQuote = {
  key: string
  label: string
  price: number
  change: number
  change_pct: number
  currency?: string
  as_of?: string
  stale?: boolean
  source?: string
}

export type MarketQuotesPayload = {
  quotes: MarketQuote[]
  errors?: string[]
}

export type MarketHistoryPayload = {
  symbol: string
  points: Array<{ date: string; close: number }>
  stale?: boolean
  source?: string
}

export type MarketIndicatorsPayload = {
  symbol: string
  trailing_vol_22d?: number | null
  return_7d_pct?: number | null
  as_of?: string
  stale?: boolean
}

export type CorridorCategory = 'sea' | 'land' | 'strategic'
export type CargoFocus = 'goods' | 'energy' | 'both'

export type CorridorRow = {
  corridor?: string
  corridor_name?: string
  category?: CorridorCategory
  corridor_risk?: number
  corridor_risk_7ma?: number
  corridor_risk_30ma?: number
  operational_risk?: number
  threat_index?: number
  energy_risk?: number
  goods_risk?: number
  energy_exposure?: number
  goods_exposure?: number
  corridor_hit_count?: number
  gpr_sum?: number
  score_status?: string
  action_label?: string
  date?: string
}

export type CorridorsPayload = {
  date?: string | null
  index_start?: string
  disclaimer?: string
  metadata?: Record<string, {
    id?: string
    name?: string
    category?: CorridorCategory
    energy_exposure?: number
    goods_exposure?: number
    exposure_source?: string
    centroid?: { lat: number; lon: number }
    waypoints?: [number, number][]
  }>
  corridors?: CorridorRow[]
  data_source?: 'postgres' | 'csv'
  updated_at?: string
  refresh_interval_minutes?: number
  stale_warning?: string | null
}

export type DualSignalPayload = {
  index_start?: string
  geopolitical?: {
    as_of?: string
    gpr_index?: number
    gpr_7ma?: number
    gpr_30ma?: number
    regime?: string
    change_7d_pct?: number | null
    geo_percentile?: number
    geo_percentile_confidence?: 'low' | 'normal'
    index_days?: number
    gpr_threats?: number
    gpr_acts?: number
    top_corridor?: string
    driving_events?: NewsArticle[]
  }
  nifty_volatility?: {
    available?: boolean
    reason?: string
    vol_forecast_5d?: number
    regime?: string
    high_vol_prob?: number
    trailing_vol_22d?: number
    return_7d_pct?: number | null
    vol_percentile?: number | null
    model?: string
  }
  joint_stress?: {
    stress_score?: number | null
    stress_regime?: string
    narrative?: string
    geo_percentile?: number
    vol_percentile?: number | null
  }
  historical_analog?: {
    query?: string
    sample_days?: number
    nifty_vol_median?: number | null
    nifty_return_median?: number | null
    notable_events?: string[]
  }
  disclaimer?: string
  driving_events_meta?: {
    candidates_scanned?: number
    geo_market_pass?: number
    geo_only_pass?: number
    returned?: number
    gate_b_relaxed?: boolean
  }
}

export type EventsFeedParams = {
  theme?: string
  corridor?: string
  tier?: string | number
  limit?: number
  tagged_only?: boolean
}

export function corridorRiskLabel(
  risk: number,
  scoreStatus?: string | null,
): { label: string; className: string } {
  if (scoreStatus === 'insufficient_history') {
    return { label: 'Calibrating', className: 'text-corridor-muted' }
  }
  if (risk >= 50) return { label: 'High', className: 'text-error' }
  if (risk >= 20) return { label: 'Medium', className: 'text-tertiary' }
  return { label: 'Low', className: 'text-secondary' }
}

export function formatArticleTime(value?: string): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value.slice(0, 10)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function formatPrice(price: number, currency?: string): string {
  if (currency === 'USD') return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Calls GET /health — a lightweight "is the backend alive and how fresh is
// its data" check. Returns overall status plus the latest dates for each
// data type (GPR score, corridor scores, news). Used by AppChrome/Footer to
// show the "Live" / "Degraded" status dot.
export function fetchHealth() {
  return fetchJSON<HealthPayload>('/health')
}

// Calls GET /api/events/feed — the raw, filterable news feed (by theme,
// corridor, priority tier, result limit). Returns a list of NewsArticle
// objects. Used by the News page whenever the user applies a filter.
export function fetchEventsFeed(params: EventsFeedParams = {}) {
  const qs = new URLSearchParams()
  if (params.theme) qs.set('theme', params.theme)
  if (params.corridor) qs.set('corridor', params.corridor)
  if (params.tier != null) qs.set('tier', String(params.tier))
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.tagged_only) qs.set('tagged_only', '1')
  const q = qs.toString()
  return fetchJSON<{ events: NewsArticle[]; source?: string }>(`/api/events/feed${q ? `?${q}` : ''}`)
}

// Calls GET /api/news/image?link=... — asks the backend to look up (or
// scrape) a thumbnail image URL for one article, given its link. Returns just
// the image URL (or null if none was found). Used by useArticleImage.ts.
export function fetchNewsImage(link: string) {
  const qs = new URLSearchParams({ link })
  return fetchJSON<{ image_url: string | null }>(`/api/news/image?${qs}`).then((r) => r.image_url)
}

export function corridorTrend(history: CorridorRow[]): 'rising' | 'falling' | 'stable' {
  if (history.length < 2) return 'stable'
  const scores = history
    .map((row) => Number(row.operational_risk ?? row.corridor_risk_7ma ?? row.corridor_risk ?? 0))
    .filter(Number.isFinite)
  if (scores.length < 2) return 'stable'
  const latest = scores[scores.length - 1]
  const prior = scores[scores.length - 2]
  if (latest > prior + 2) return 'rising'
  if (latest < prior - 2) return 'falling'
  return 'stable'
}

export function corridorOperationalRisk(row: CorridorRow): number {
  const value = row.operational_risk ?? row.corridor_risk_7ma ?? row.corridor_risk
  return Number.isFinite(Number(value)) ? Number(value) : 0
}

// Calls GET /api/market/dual-signal — the combined "news risk + market
// volatility" signal used on the Macro page (geopolitical score, NIFTY vol
// forecast, joint stress score, historical analog). Pass `refresh: true` to
// force the backend to recompute instead of serving a cached value.
export function fetchDualSignal(refresh = false) {
  const qs = refresh ? '?refresh=1' : ''
  return fetchJSON<DualSignalPayload>(`/api/market/dual-signal${qs}`)
}

export const MARKET_SYMBOL_ORDER = ['nifty', 'sensex', 'india_vix', 'usd_inr', 'brent'] as const

export const MARKET_SYMBOL_LABELS: Record<(typeof MARKET_SYMBOL_ORDER)[number], string> = {
  nifty: 'NIFTY 50',
  sensex: 'SENSEX',
  india_vix: 'INDIA VIX',
  usd_inr: 'USD/INR',
  brent: 'Brent Crude',
}

export function formatCorridorName(id?: string, name?: string): string {
  if (name && name !== id) return name
  if (!id) return '—'
  return id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function orderMarketQuotes(quotes: MarketQuote[]): MarketQuote[] {
  const byKey = new Map(quotes.map((q) => [q.key, q]))
  return MARKET_SYMBOL_ORDER.map((k) => byKey.get(k)).filter(Boolean) as MarketQuote[]
}

export type QualityCheckStatus = 'pass' | 'fail' | 'warn' | 'na'

export type QualityCheck = {
  id: string
  category: 'pipeline' | 'gpr' | 'corridor' | 'market' | 'nlp'
  title: string
  value: string | number | null
  threshold: string
  status: QualityCheckStatus
  why: string
  tier?: 'headline' | 'detail' | 'informational'
  freshness?: 'live' | 'offline' | 'stale'
  validated_at?: string | null
  source?: { type: string; path?: string | null; updated_at?: string }
  detail?: Record<string, unknown>
}

export type QualitySummaryHeadline = {
  checks_total: number
  checks_passing: number
  checks_failing?: number
  checks_warn?: number
  overall_status: 'pass' | 'warn' | 'fail'
}

export type QualityReportMeta = {
  cached_at?: string | null
  validation_artifacts_as_of?: string | null
  live_index_through?: string | null
  live_gpr_source?: string | null
  is_stale?: boolean
  stale_reason?: string | null
}

export type HealthSnapshot = {
  status?: string
  gpr_latest_date?: string | null
  stale_warning?: string | null
  articles_total?: number
  timestamp?: string
}

export type QualityReport = {
  generated_at: string
  as_of: {
    gpr_latest_date: string | null
    pipeline_last_run: string | null
  }
  report_meta?: QualityReportMeta
  summary: QualitySummaryHeadline & {
    checks_na?: number
    headline?: QualitySummaryHeadline
  }
  coverage: Array<{
    id: string
    label: string
    value: string | number
    unit?: string
    status?: QualityCheckStatus | null
  }>
  checks: QualityCheck[]
  pipeline: {
    ingestion: {
      total_articles?: number
      tier_articles?: number
      ingest_yield_7d_pct?: number | null
      fetched_7d?: number
      ingested_7d?: number
      sources_healthy?: number
      sources_total?: number
      sources_unhealthy?: number
      feed_health?: Record<
        string,
        { consecutive_failures?: number; last_success?: string | null; last_error?: string | null }
      >
      gpr_index_days?: number
      gpr_latest_date?: string | null
      description?: string
    }
    nlp: {
      tier_articles?: number
      nlp_complete?: number
      nlp_pending?: number
      coverage_pct?: number | null
      corridor_tagging?: {
        passed?: number
        total?: number
        pass_rate_pct?: number | null
        cases?: Array<{ label: string; pass: boolean }>
      }
      description?: string
    }
    stages_30d?: Array<{ stage: string; status: string; count: number }>
  }
  methodology: Array<{
    step: number
    title: string
    body: string
    layer: string
  }>
  disclaimer: string
  status?: PlatformStatusSlim | null
  health?: HealthSnapshot | null
}

// The six functions below each call one "page bundle" endpoint. Rather than
// having a page fire off five separate requests (health, quotes, corridors,
// news, ...), the backend pre-joins everything one page needs into a single
// JSON response — so each page component only needs ONE useQuery() call.

// Calls GET /api/pages/home — everything the Home page needs in one request:
// health, current GPR score, corridor list, market quotes, dual signal.
export function fetchPageHome() {
  return fetchJSON<HomePageBundle>('/api/pages/home')
}

// Calls GET /api/pages/macro — everything the Market Stress Monitor page
// needs: dual signal, market quotes + indicators, GPR history, corridors.
export function fetchPageMacro() {
  return fetchJSON<MacroPageBundle>('/api/pages/macro')
}

// Calls GET /api/pages/news?limit=N — the News page's headline feed plus the
// current GPR score/history, capped at `limit` articles (default 50).
export function fetchPageNews(limit = 50) {
  return fetchJSON<NewsPageBundle>(`/api/pages/news?limit=${limit}`)
}

// Calls GET /api/pages/corridor?corridor=X&limit=N — corridor risk scores
// plus recent headlines, optionally scoped to one `corridor` search term.
export function fetchPageCorridor(corridor?: string, limit = 40) {
  const qs = new URLSearchParams({ limit: String(limit) })
  if (corridor) qs.set('corridor', corridor)
  return fetchJSON<CorridorPageBundle>(`/api/pages/corridor?${qs}`)
}

// Calls GET /api/pages/portfolio — GPR score, dual signal, and market quotes
// used to drive the (illustrative) Portfolio Exposure page.
export function fetchPagePortfolio() {
  return fetchJSON<PortfolioPageBundle>('/api/pages/portfolio')
}

// Calls GET /api/pages/quality — the full data-quality/validation report
// shown on the Accuracy/Quality page. Pass `refresh: true` to make the
// backend recompute the live checks instead of returning a cached report.
export function fetchPageQuality(refresh = false) {
  const qs = refresh ? '?refresh=1' : ''
  return fetchJSON<QualityReport>(`/api/pages/quality${qs}`)
}

