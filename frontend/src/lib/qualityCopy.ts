export const QUALITY_EYEBROW = 'Platform Quality'

export const QUALITY_TITLE = 'Can you trust these numbers?'

export const QUALITY_SUBTITLE =
  'Live data health and benchmark checks for India risk, trade routes, and market stress — updated throughout the day.'

export const SECTION_RIGHT_NOW = 'Right now'
export const SECTION_RIGHT_NOW_SUB =
  'Is data flowing, fresh, and ready to use on the dashboards?'

export const SECTION_PROVEN = 'Proven checks'
export const SECTION_PROVEN_SUB =
  'Key benchmarks we run against published standards and labelled test cases.'

export const SECTION_HOW_BUILT = 'How we build scores'
export const SECTION_HOW_BUILT_SUB =
  'From news events to route-level risk — every step documented.'

export const SECTION_TECHNICAL = 'Technical details'
export const SECTION_TECHNICAL_SUB =
  'Full check list with thresholds, source files, and validation dates.'

export const TOGGLE_SHOW_TECHNICAL = 'Show technical details'
export const TOGGLE_HIDE_TECHNICAL = 'Hide technical details'

export const CATEGORY_INTROS: Record<string, string> = {
  pipeline: 'Live status of news feeds and article processing.',
  gpr: 'Risk index validated against the academic Caldara-Iacoviello benchmark.',
  corridor: 'Trade route scores tested for geographic specificity.',
  market: 'Whether the risk index adds value for NIFTY volatility forecasting.',
  nlp: 'Location tagging on hand-checked sample articles.',
}

export const METHODOLOGY_STEPS = [
  {
    step: 1,
    title: 'Collect news',
    body: 'RSS and GDELT articles about India and trade routes, deduplicated daily.',
    layer: 'sources' as const,
  },
  {
    step: 2,
    title: 'Tag & classify',
    body: 'Themes, locations, and route labels across 12 India-relevant trade corridors.',
    layer: 'processing' as const,
  },
  {
    step: 3,
    title: 'Build indices',
    body: 'Daily India risk index plus route scores weighted by energy and goods exposure.',
    layer: 'index' as const,
  },
  {
    step: 4,
    title: 'Validate',
    body: 'Academic benchmarks, route tests, and market backtests — results shown on this page.',
    layer: 'validation' as const,
  },
]

export const DATA_ARCHITECTURE_LAYERS = [
  { id: 'sources', label: 'RSS / GDELT', tag: 'Live' },
  { id: 'nlp', label: 'Tagging engine', tag: 'Processing' },
  { id: 'index', label: 'Risk + route scores', tag: 'Index' },
  { id: 'delivery', label: 'Dashboards', tag: 'Delivery' },
]

export const CHECK_CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'pipeline', label: 'Data feeds' },
  { id: 'gpr', label: 'Risk index' },
  { id: 'corridor', label: 'Routes' },
  { id: 'market', label: 'Market' },
  { id: 'nlp', label: 'Locations' },
] as const

export type CheckCategoryFilter = (typeof CHECK_CATEGORIES)[number]['id']

export function qualityStatusLine(gprDate?: string | null, pipelineRun?: string | null): string {
  const parts: string[] = []
  if (gprDate) parts.push(`Risk data through ${gprDate.slice(0, 10)}`)
  if (pipelineRun) parts.push(`last refresh ${new Date(pipelineRun).toLocaleString()}`)
  return parts.join(' · ') || 'Waiting for pipeline data'
}
