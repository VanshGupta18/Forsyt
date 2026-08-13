const API_BASE = String(import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

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
}

export type StatsPayload = {
  total_articles?: number
  recent_cycles?: unknown[]
  feed_health?: Record<string, unknown>
}

export type NewsArticle = {
  title?: string
  link?: string
  source?: string
  tier?: number
  published_at?: string
  scraped_at?: string
  nlp_themes?: string
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
  }>
  corridors?: CorridorRow[]
}

export type CorridorHistoryPayload = {
  corridor?: string
  history?: CorridorRow[]
  error?: string
}

export type DualSignalPayload = {
  geopolitical?: {
    as_of?: string
    gpr_index?: number
    gpr_7ma?: number
    gpr_30ma?: number
    regime?: string
    change_7d_pct?: number
    geo_percentile?: number
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
}

export type EventsFeedParams = {
  theme?: string
  corridor?: string
  tier?: string | number
  limit?: number
  tagged_only?: boolean
}

export function corridorRiskLabel(risk: number): { label: string; className: string } {
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

export function fetchGprCurrent() {
  return fetchJSON<GprCurrent>('/api/gpr/current')
}

export function fetchGprHistory(limit = 800) {
  return fetchJSON<GprHistoryPayload>(`/api/gpr/history?limit=${limit}`)
}

export function fetchHealth() {
  return fetchJSON<HealthPayload>('/health')
}

export function fetchStats() {
  return fetchJSON<StatsPayload>('/stats')
}

export function fetchRecentNews(limit = 50) {
  return fetchJSON<{ articles: NewsArticle[] }>(`/api/news/recent?limit=${limit}`)
}

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

export function fetchCorridors() {
  return fetchJSON<CorridorsPayload>('/api/corridors')
}

export function fetchCorridorHistory(corridorId: string, limit = 30) {
  return fetchJSON<CorridorHistoryPayload>(`/api/corridors/${encodeURIComponent(corridorId)}?limit=${limit}`)
}

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

export function fetchMarketQuotes(symbols?: string[]) {
  const qs = symbols?.length ? `?symbols=${symbols.join(',')}` : ''
  return fetchJSON<MarketQuotesPayload>(`/api/market/quotes${qs}`)
}

export function fetchMarketHistory(symbol = 'nifty', period = '3mo') {
  return fetchJSON<MarketHistoryPayload>(`/api/market/history?symbol=${symbol}&period=${period}`)
}

export function fetchMarketIndicators(symbol = 'nifty') {
  return fetchJSON<MarketIndicatorsPayload>(`/api/market/indicators?symbol=${symbol}`)
}

export type AccuracyMetricsPayload = {
  generated_at?: string
  disclaimer?: string
  ingestion?: {
    total_articles?: number
    tier_articles?: number
    ingest_yield_7d_pct?: number | null
    discard_rate_7d_pct?: number | null
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
  nlp?: {
    tier_articles?: number
    nlp_complete?: number
    nlp_pending?: number
    coverage_pct?: number | null
    corridor_tagging?: {
      passed?: number
      total?: number
      pass_rate_pct?: number | null
      cases?: Array<{ label: string; pass: boolean }>
      description?: string
    }
    description?: string
  }
  gpr_index?: {
    benchmarks?: Array<{
      comparison?: string
      pearson_r?: number | null
      pass?: boolean
      days_overlap?: number
    }>
    caldara_ma30_r?: number | null
    caldara_ma30_pass?: boolean | null
    target_r?: number
    description?: string
  }
  corridors?: {
    corridors_validated?: number
    parent_leakage_pass_rate_pct?: number | null
    parent_leakage_passed?: number
    corridors?: Array<{ corridor?: string; parent_correlation?: number; pass?: boolean }>
    description?: string
  }
  nifty_volatility?: {
    market_only_roc_auc?: number
    market_plus_gpr_roc_auc?: number
    gpr_incremental_roc_auc?: number
    horizon_days?: number
    source?: string
    note?: string
    description?: string
    error?: string
  }
}

export function fetchAccuracyMetrics(refreshVol = false) {
  const qs = refreshVol ? '?refresh_vol=1' : ''
  return fetchJSON<AccuracyMetricsPayload>(`/api/metrics/accuracy${qs}`)
}
