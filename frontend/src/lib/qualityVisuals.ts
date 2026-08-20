export type SourceNode = {
  id: string
  label: string
  color: string
  angle: number
}

/** Hub-and-spoke sources — short labels to avoid SVG clipping */
export const SOURCE_HUB_NODES: SourceNode[] = [
  { id: 'gdelt', label: 'GDELT', color: '#4a90d9', angle: -90 },
  { id: 'rss', label: 'RSS', color: '#4edea3', angle: -18 },
  { id: 'nse', label: 'NIFTY', color: '#f5b800', angle: 54 },
  { id: 'caldara', label: 'Benchmark', color: '#a78bfa', angle: 126 },
  { id: 'corridors', label: 'Routes', color: '#ff6b6b', angle: 198 },
]

export const METHODOLOGY_STEP_THEMES = [
  { bg: 'rgba(74, 144, 217, 0.12)', border: '#4a90d9', text: '#6eb5ff' },
  { bg: 'rgba(78, 222, 163, 0.12)', border: '#4edea3', text: '#7ef0c0' },
  { bg: 'rgba(245, 184, 0, 0.12)', border: '#f5b800', text: '#ffd54f' },
  { bg: 'rgba(255, 107, 107, 0.12)', border: '#ff6b6b', text: '#ff8a8a' },
] as const

export const FLOW_PIPELINE_NODES = [
  { id: 'signals', label: 'News & events', sub: 'GDELT · RSS · locations', color: '#4a90d9' },
  { id: 'engine', label: 'Scoring engine', sub: 'Themes · routes · risk index', color: '#4edea3' },
  { id: 'intel', label: 'Dashboards', sub: 'Validated · traceable', color: '#adc6ff' },
] as const
