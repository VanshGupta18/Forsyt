// ---------------------------------------------------------------------------
// Like macroCopy.ts, this file is pure logic + copywriting — no UI — for the
// Trade & Corridor Risk page. A "corridor" is a shipping lane or land border
// crossing (e.g. Strait of Hormuz, India–Pakistan Attari). Each one gets a
// 0-100+ "operational risk" score from the backend (see corridorOperationalRisk
// in api.ts). The functions below translate that raw number into the plain
// business language shown on screen: a risk TIER ("Normal"/"Watch"/"High
// alert"), a text color class, an accent color for chart lines, and advisory
// copy. The tier thresholds — used consistently everywhere in this file — are:
//   risk >= 50  → "High"   (shown to users as "High alert")
//   risk >= 20  → "Medium" (shown to users as "Watch")
//   otherwise   → "Low"    (shown to users as "Normal")
// (The actual >= 50 / >= 20 cutoffs live in `corridorRiskLabel()` in api.ts —
// everything here just re-labels/re-colors whatever tier that function picks.)
// ---------------------------------------------------------------------------
import { corridorOperationalRisk, corridorRiskLabel, type CorridorRow } from './api'

export const CORRIDOR_PAGE_DISCLAIMER =
  'Scores reflect recent news about each route — not a guarantee of disruption. Updated hourly in cloud.'

export const CORRIDOR_DATA_REFRESH_NOTE = 'updates hourly in cloud'

export function corridorDataThroughLine(date: string | null | undefined): string {
  const through = date ? `Data through ${date}` : 'Waiting for corridor data'
  return `${through} · ${CORRIDOR_DATA_REFRESH_NOTE}`
}

export function formatPipelineRunAt(value?: string | null): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value.slice(0, 16)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function corridorStatusLine(
  date: string | null | undefined,
  pipelineRunAt?: string | null,
): string {
  const base = corridorDataThroughLine(date)
  const run = formatPipelineRunAt(pipelineRunAt)
  return run ? `${base} · recomputed ${run}` : base
}

export const OPERATIONAL_SCORE_NOTE = '7-day operational average'

export const CORRIDOR_EYEBROW = 'Live route monitoring'

export const CORRIDOR_PAGE_SUBTITLE =
  'See which shipping lanes and border crossings need attention before you book freight.'

export const CORRIDOR_HEADLINES_TITLE = 'Latest news for this route'

export const SCORE_LABELS = {
  threat: 'News activity',
  goods: 'Impact on shipments',
  energy: 'Fuel & energy impact',
} as const

// Turns a raw risk tier ("High"/"Medium"/"Low", from corridorRiskLabel in
// api.ts) into the friendlier word shown in the UI. `scoreStatus ===
// 'insufficient_history'` overrides everything else — a corridor with too
// little historical data yet is "Calibrating" regardless of its raw score,
// so a noisy early number can't be mistaken for a confident "High alert".
export function businessTierLabel(risk: number, scoreStatus?: string | null): string {
  const { label } = corridorRiskLabel(risk, scoreStatus)
  if (label === 'Calibrating') return 'Calibrating'
  if (label === 'High') return 'High alert'
  if (label === 'Medium') return 'Watch'
  return 'Normal'
}

export function businessTierClass(risk: number, scoreStatus?: string | null): string {
  const { label } = corridorRiskLabel(risk, scoreStatus)
  if (label === 'Calibrating') return 'text-corridor-muted'
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

export function spikeBadgeDetail(): string {
  return 'Today’s daily score is elevated vs the 7-day average shown above.'
}

export function tierAccentColor(risk: number, scoreStatus?: string | null): string {
  const { label } = corridorRiskLabel(risk, scoreStatus)
  if (label === 'Calibrating') return 'var(--corridor-accent-clear)'
  if (label === 'High') return 'var(--corridor-accent-alert)'
  if (label === 'Medium') return 'var(--corridor-accent-watch)'
  return 'var(--corridor-accent-clear)'
}

// Rounds the corridor's operational risk score to a whole number for
// display (the underlying score can have decimals; showing "42" reads
// cleaner on a dashboard than "42.37").
export function displayStressScore(row: CorridorRow | Record<string, unknown>): number {
  return Math.round(corridorOperationalRisk(row as CorridorRow))
}
