import { corridorOperationalRisk, corridorRiskLabel, type CorridorRow } from './api'

export const CORRIDOR_PAGE_DISCLAIMER =
  'Scores reflect recent news about each route — not a guarantee of disruption. Updated daily.'

export const CORRIDOR_EYEBROW = 'Live route monitoring'

export const CORRIDOR_PAGE_SUBTITLE =
  'See which shipping lanes and border crossings need attention before you book freight.'

export const CORRIDOR_HEADLINES_TITLE = 'Latest news for this route'

export const SCORE_LABELS = {
  threat: 'News activity',
  goods: 'Impact on shipments',
  energy: 'Fuel & energy impact',
} as const

export function businessTierLabel(risk: number): string {
  const { label } = corridorRiskLabel(risk)
  if (label === 'High') return 'High alert'
  if (label === 'Medium') return 'Watch'
  return 'Normal'
}

export function businessTierClass(risk: number): string {
  const { label } = corridorRiskLabel(risk)
  if (label === 'High') return 'text-corridor-alert'
  if (label === 'Medium') return 'text-corridor-watch'
  return 'text-corridor-clear'
}

export function businessActionLabel(action?: string | null): string {
  if (!action) return 'Normal operations'
  if (action === 'Monitor closely') return 'Watch this route'
  if (action === 'Calibrating') return 'Still learning this route'
  return action
}

export function newsMentionsLine(hitCount: number): string {
  if (hitCount === 0) return 'No news mentions today for this route.'
  return `${hitCount} news mention${hitCount === 1 ? '' : 's'} today`
}

export function watchlistAlertLine(count: number): string {
  return `${count} pinned route${count > 1 ? 's' : ''} need attention this week — review contingency plans.`
}

export function calibratingBadge(): string {
  return 'Still building a picture for this route'
}

export function spikeBadge(): string {
  return 'Unusual activity today'
}

export function tierAccentColor(risk: number): string {
  const { label } = corridorRiskLabel(risk)
  if (label === 'High') return 'var(--corridor-accent-alert)'
  if (label === 'Medium') return 'var(--corridor-accent-watch)'
  return 'var(--corridor-accent-clear)'
}

export function displayStressScore(row: CorridorRow | Record<string, unknown>): number {
  return Math.round(corridorOperationalRisk(row as CorridorRow))
}

export function routeStressTier(row: CorridorRow | Record<string, unknown>): string {
  const op = Number(
    (row as CorridorRow).operational_risk ??
      (row as CorridorRow).corridor_risk_7ma ??
      (row as CorridorRow).corridor_risk ??
      0,
  )
  return businessTierLabel(op)
}
