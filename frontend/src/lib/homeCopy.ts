import { formatPipelineRunAt } from './corridorCopy'

export const HOME_EYEBROW = 'Live intelligence for India'

export const HOME_TITLE = 'See headline risk, market stress, and corridor disruption — today.'

export const HOME_SUBTITLE =
  'Geopolitical headlines, market volatility, and trade route scores — in one place for Indian decision-makers.'

export const HOME_DISCLAIMER =
  'Scores reflect recent news we track — not trading advice or shipping instructions.'

export function homeStatusLine(gprDate?: string | null, pipelineRunAt?: string | null): string {
  const through = gprDate ? `Geo data through ${gprDate.slice(0, 10)}` : 'Waiting for geo data'
  const run = formatPipelineRunAt(pipelineRunAt)
  return run ? `${through} · recomputed ${run}` : through
}

export function gprRegimeFromIndex(idx?: number | null): string {
  if (idx == null || !Number.isFinite(idx)) return ''
  if (idx >= 135) return 'ELEVATED'
  if (idx >= 100) return 'MODERATE'
  return 'LOW'
}
