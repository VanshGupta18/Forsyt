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
  const upperKey = upper.replace(/[\s-]+/g, '_')
  if (THEME_DISPLAY_LABELS[upperKey]) return THEME_DISPLAY_LABELS[upperKey]
  return humanizeTopicLabel(trimmed)
}

export function primaryTheme(article?: NewsArticle): string {
  const raw = article?.nlp_themes?.split(',')[0]?.trim()
  return raw ? themeDisplayLabel(raw) : 'General'
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
  const theme = primaryTheme(article)
  if (theme !== 'General') parts.push(theme)
  return parts.length ? parts.join(' · ') : 'Recent headline'
}
