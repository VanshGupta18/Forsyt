import type { NewsArticle } from './api'
import { formatPipelineRunAt } from './corridorCopy'

export const NEWS_EYEBROW = 'Live headline monitoring'

export const NEWS_PAGE_TITLE = 'News Intelligence'

export const NEWS_PAGE_SUBTITLE =
  'See which geopolitical headlines matter for Indian markets and trade routes — filtered by topic and priority.'

export const NEWS_PAGE_DISCLAIMER =
  'Headlines reflect recent news we track — not trading advice or shipping instructions.'

export const NEWS_DATA_REFRESH_NOTE = 'updates every 10 minutes'

export const NEWS_THEME_PRESETS = ['CONFLICT', 'MILITARY', 'TRADE', 'TERROR'] as const

export const THEME_DISPLAY_LABELS: Record<string, string> = {
  CONFLICT: 'Conflict',
  MILITARY: 'Military',
  TRADE: 'Trade routes',
  TERROR: 'Terror',
}

export const NEWS_TOP_STORIES_TITLE = 'Top stories today'

export const NEWS_RISK_CONTEXT_TITLE = 'Risk context'

export const NEWS_FEED_TITLE = 'All headlines'

export const NEWS_TICKER_TITLE = 'More headlines'

export const NEWS_MOST_COVERED_LABEL = 'Most covered'

const TOPIC_BUCKET_KEYS = ['CONFLICT', 'MILITARY', 'TRADE', 'TERROR'] as const
type TopicBucketKey = (typeof TOPIC_BUCKET_KEYS)[number]

/** GPR / NLP taxonomy codes → editorial bucket */
const TOPIC_CODE_BUCKET: Record<string, TopicBucketKey> = {
  ARMEDCONFLICT: 'CONFLICT',
  INVASION: 'CONFLICT',
  COUP: 'CONFLICT',
  ETHNIC_VIOLENCE: 'CONFLICT',
  GENOCIDE: 'CONFLICT',
  BORDER_DISPUTE: 'CONFLICT',
  MARITIME_DISPUTE: 'CONFLICT',
  PROXY_WAR: 'CONFLICT',
  WAR_CRIME: 'CONFLICT',
  DIPLOMATIC_CRISIS: 'CONFLICT',
  BLOCKADE: 'TRADE',
  NUCLEAR_WEAPONS: 'MILITARY',
  NUCLEAR: 'MILITARY',
  BALLISTIC_MISSILES: 'MILITARY',
  CHEMICAL_WEAPONS: 'MILITARY',
  BIOLOGICAL_WEAPONS: 'MILITARY',
  TAX_FNCACT_MILITARY: 'MILITARY',
  TAX_FNCACT_SOLDIER: 'MILITARY',
  TAX_FNCACT_REBEL: 'MILITARY',
  ESPIONAGE: 'MILITARY',
  CYBERATTACK: 'MILITARY',
  TERROR: 'TERROR',
  TERROR_ATTACK: 'TERROR',
  TAX_FNCACT_TERRORIST: 'TERROR',
  SANCTION: 'TRADE',
}

export function newsStatusLine(
  gprDate: string | null | undefined,
  pipelineRunAt?: string | null,
): string {
  const through = gprDate
    ? `News risk data through ${gprDate.slice(0, 10)}`
    : 'Waiting for news risk data'
  const base = `${through} · ${NEWS_DATA_REFRESH_NOTE}`
  const run = formatPipelineRunAt(pipelineRunAt)
  return run ? `${base} · last updated ${run}` : base
}

function normalizeTopicToken(raw: string): string {
  return raw.trim().toUpperCase().replace(/[\s-]+/g, '_')
}

/** Split nlp_themes — pipeline uses semicolons; some rows use commas. */
export function parseThemeTokens(raw?: string | null): string[] {
  if (!raw?.trim()) return []
  return raw
    .split(/[,;]+/)
    .map((t) => t.trim())
    .filter(Boolean)
}

function bucketFromToken(token: string): TopicBucketKey | null {
  const key = normalizeTopicToken(token)
  if (TOPIC_CODE_BUCKET[key]) return TOPIC_CODE_BUCKET[key]

  if (/NUCLEAR|BALLISTIC|MISSILE|MILITARY|SOLDIER|WEAPON|CYBER|ESPIONAGE/.test(key)) return 'MILITARY'
  if (/TERROR|EXTREMIST|JIHAD|BOMB|BLAST/.test(key)) return 'TERROR'
  if (/SANCTION|TRADE|EMBARGO|BLOCKADE|SHIPPING|PORT/.test(key)) return 'TRADE'
  if (/CONFLICT|WAR|INVAS|BORDER|FIGHT|COUP|VIOLENCE|DISPUTE/.test(key)) return 'CONFLICT'

  const preset = key.replace(/[\s-]+/g, '_') as TopicBucketKey
  if (TOPIC_BUCKET_KEYS.includes(preset)) return preset

  return null
}

function humanizeTopicLabel(raw: string): string {
  return raw
    .trim()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

export function themeDisplayLabel(theme?: string): string {
  if (!theme?.trim()) return 'General'
  const trimmed = theme.trim()
  const upper = trimmed.toUpperCase()
  if (THEME_DISPLAY_LABELS[upper]) return THEME_DISPLAY_LABELS[upper]
  const bucket = bucketFromToken(trimmed)
  if (bucket) return THEME_DISPLAY_LABELS[bucket]
  return humanizeTopicLabel(trimmed)
}

/** Plain-language topic for one article — maps jargon tags to editorial buckets. */
export function articleTopicLabel(article?: NewsArticle): string {
  const tokens = parseThemeTokens(article?.nlp_themes)
  for (const token of tokens) {
    const bucket = bucketFromToken(token)
    if (bucket) return THEME_DISPLAY_LABELS[bucket]
  }
  if (tokens.length) return themeDisplayLabel(tokens[0])
  return 'General'
}

/** @deprecated Use articleTopicLabel — kept for existing imports */
export function primaryTheme(article?: NewsArticle): string {
  return articleTopicLabel(article)
}

/** Count editorial buckets across a feed for the pulse strip. */
export function dominantTopicLabel(articles: NewsArticle[]): string {
  const counts = new Map<string, number>()
  for (const article of articles) {
    const label = articleTopicLabel(article)
    if (label === 'General') continue
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  let best = '—'
  let max = 0
  for (const [label, count] of counts) {
    if (count > max) {
      max = count
      best = label
    }
  }
  return best
}

export function priorityLabel(tier?: number): string {
  if (tier === 1) return 'High priority'
  if (tier === 2) return 'Standard'
  return 'Unranked'
}

export function tierHotLabel(tier?: number): string {
  return tier === 1 ? 'Breaking' : 'Lead story'
}

export function tierBadgeClass(tier?: number): string {
  return tier === 1 ? 'text-corridor-alert' : 'text-corridor-muted'
}

export function newsEmptyLine(): string {
  return 'No headlines match these filters — try All stories or clear the route filter.'
}

export function newsBreakingEmptyLine(): string {
  return 'No high-priority headlines right now — try All stories.'
}

export function briefWhyLine(article: NewsArticle): string {
  const parts: string[] = []
  if (article.tier === 1) parts.push('High priority')
  const topic = articleTopicLabel(article)
  if (topic !== 'General') parts.push(topic)
  return parts.length ? parts.join(' · ') : 'Recent headline'
}
