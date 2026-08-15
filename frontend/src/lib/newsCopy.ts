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

export const NEWS_DRAWER_TITLE = 'Story details'

export const NEWS_WHY_SHOWING_TITLE = "Why we're showing this"

export const NEWS_TOPICS_TITLE = 'Topics'

export const NEWS_SEE_ALSO_TITLE = 'See also'

export const NEWS_HERO_WHY_CTA = 'Why this story'

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

export function themeDisplayLabel(theme?: string): string {
  if (!theme?.trim()) return 'General'
  const upper = theme.trim().toUpperCase()
  if (THEME_DISPLAY_LABELS[upper]) return THEME_DISPLAY_LABELS[upper]
  return theme.trim().charAt(0).toUpperCase() + theme.trim().slice(1).toLowerCase()
}

export function primaryTheme(article?: NewsArticle): string {
  const raw = article?.nlp_themes?.split(',')[0]?.trim()
  return raw ? themeDisplayLabel(raw) : 'General'
}

export function parseThemes(article?: NewsArticle): string[] {
  if (!article?.nlp_themes?.trim()) return []
  return article.nlp_themes
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => themeDisplayLabel(t))
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

export function freshnessLabel(published?: string, scraped?: string): string {
  const value = published || scraped
  if (!value) return 'Timing unknown'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Timing unknown'
  const hours = (Date.now() - d.getTime()) / 3_600_000
  if (hours < 1) return 'Published within the hour'
  if (hours < 24) return 'Published today'
  if (hours < 72) return 'Published in the last 3 days'
  return 'Older headline'
}

export function trustTierExplanation(tier?: number): string {
  if (tier === 1) return 'High priority — flagged as especially relevant to markets and trade routes.'
  if (tier === 2) return 'Standard — useful background; lower immediate weight.'
  return 'Still being reviewed for priority.'
}

export function tagStatusLine(article?: NewsArticle): string {
  const themes = parseThemes(article)
  if (themes.length) {
    return `${themes.length} topic${themes.length === 1 ? '' : 's'} identified`
  }
  return 'Topics still being classified'
}

export function briefWhyLine(article: NewsArticle): string {
  const parts: string[] = []
  if (article.tier === 1) parts.push('High priority')
  const theme = primaryTheme(article)
  if (theme !== 'General') parts.push(theme)
  return parts.length ? parts.join(' · ') : 'Recent headline'
}

export function crossLinkHints(
  article?: NewsArticle,
  corridorFilter?: string,
): { macro?: boolean; corridor?: boolean } {
  const rawThemes = (article?.nlp_themes ?? '').toUpperCase()
  const macro =
    article?.tier === 1 ||
    ['CONFLICT', 'MILITARY', 'TERROR'].some((t) => rawThemes.includes(t))
  const corridor =
    Boolean(corridorFilter) ||
    ['TRADE', 'CONFLICT', 'MILITARY'].some((t) => rawThemes.includes(t))
  return { macro, corridor }
}
