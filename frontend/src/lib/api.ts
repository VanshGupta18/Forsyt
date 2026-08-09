const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`)
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

export type HealthPayload = {
  total_articles?: number
  status?: string
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

export type CorridorsPayload = {
  date?: string | null
  corridors?: Array<{
    corridor?: string
    corridor_name?: string
    corridor_risk?: number
    threat_index?: number
    energy_risk?: number
    goods_risk?: number
  }>
}

export type DualSignalPayload = {
  geopolitical?: {
    as_of?: string
    gpr_index?: number
    regime?: string
    change_7d_pct?: number
    top_corridor?: string
    driving_events?: NewsArticle[]
  }
  nifty_volatility?: {
    vol_forecast_5d?: number
    regime?: string
    high_vol_prob?: number
    trailing_vol_22d?: number
  }
  joint_stress?: {
    stress_score?: number
    stress_regime?: string
    narrative?: string
  }
  disclaimer?: string
}

export function corridorRiskLabel(risk: number): { label: string; className: string } {
  if (risk >= 50) return { label: 'High', className: 'text-error' }
  if (risk >= 20) return { label: 'Medium', className: 'text-tertiary' }
  return { label: 'Low', className: 'text-secondary' }
}

export function fetchGprCurrent() {
  return fetchJSON<GprCurrent>('/api/gpr/current')
}

export function fetchHealth() {
  return fetchJSON<HealthPayload>('/health')
}

export function fetchRecentNews(limit = 50) {
  return fetchJSON<{ articles: NewsArticle[] }>(`/api/news/recent?limit=${limit}`)
}

export function fetchCorridors() {
  return fetchJSON<CorridorsPayload>('/api/corridors')
}

export function fetchDualSignal(refresh = false) {
  const qs = refresh ? '?refresh=1' : ''
  return fetchJSON<DualSignalPayload>(`/api/market/dual-signal${qs}`)
}
