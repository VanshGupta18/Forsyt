import type { QualityCheck, QualityCheckStatus } from './api'

import { CHECK_CATEGORIES } from './qualityCopy'

export const STATUS_PLAIN: Record<QualityCheckStatus, string> = {
  pass: 'Looks good',
  fail: 'Needs attention',
  warn: 'Worth watching',
  na: 'Not enough data yet',
}

const CATEGORY_BY_ID = Object.fromEntries(
  CHECK_CATEGORIES.filter((c) => c.id !== 'all').map((c) => [c.id, c.label]),
)

export const CHECK_PLAIN: Record<
  string,
  { title: string; explainer: string }
> = {
  gpr_caldara_ma30: {
    title: 'Matches the academic risk index',
    explainer: '30-day average tracks the Caldara-Iacoviello benchmark (target: strong match).',
  },
  gpr_caldara_ma7: {
    title: 'Short-term index tracking',
    explainer: '7-day average vs academic benchmark.',
  },
  gpr_caldara_raw_daily: {
    title: 'Raw daily index (informational)',
    explainer: 'Unsmoothed daily series — expected to be noisy; we use smoothed averages for signals.',
  },
  corridor_parent_leakage: {
    title: 'Trade routes have their own scores',
    explainer: 'Route scores should not simply mirror the India-wide risk index.',
  },
  pipeline_source_health: {
    title: 'News feeds are responding',
    explainer: 'All configured RSS sources ingesting without repeated failures.',
  },
  pipeline_nlp_coverage: {
    title: 'Articles analysed',
    explainer: 'Share of location-relevant articles with completed theme and location tagging.',
  },
  nlp_corridor_fixtures: {
    title: 'Route tagging accuracy',
    explainer: 'Hand-checked sample articles tagged to the correct trade route.',
  },
  market_vol_gpr_incremental: {
    title: 'Risk index helps predict market stress',
    explainer: 'Does the index add value beyond market data alone for NIFTY volatility?',
  },
}

export function plainCheckTitle(check: QualityCheck): string {
  return CHECK_PLAIN[check.id]?.title ?? check.title
}

export function plainCheckExplainer(check: QualityCheck): string {
  return CHECK_PLAIN[check.id]?.explainer ?? check.why
}

export function plainCategory(category: string): string {
  return CATEGORY_BY_ID[category] ?? category
}
