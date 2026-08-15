import type { NewsArticle } from './api'

export const NEWS_EYEBROW = 'Live news intelligence'

export const NEWS_PAGE_TITLE = 'News Intelligence'

export const NEWS_PAGE_SUBTITLE =
  'Tagged geopolitical intelligence from live sources — scored, filtered, and connected to market and corridor risk.'

export const NEWS_PAGE_DISCLAIMER =
  'Headlines reflect ingested news flow and NLP tags — not trading advice or operational directives.'

export const NEWS_THEME_PRESETS = ['CONFLICT', 'MILITARY', 'TRADE', 'TERROR'] as const

export const NEWS_BREAKING_TITLE = 'Breaking'

export const NEWS_INTEL_BRIEF_TITLE = 'Intel brief'

export const NEWS_MORNING_BRIEF_TITLE = 'Morning brief'

export const NEWS_FEED_TITLE = 'Intelligence feed'

export const NEWS_TICKER_TITLE = 'Latest flow'

export function newsEmptyLine(): string {
  return 'No articles match these filters — try clearing theme or corridor scope.'
}

export function newsBreakingEmptyLine(): string {
  return 'No Tier-1 stories in this feed right now.'
}

export function tierLabel(tier?: number): string {
  if (tier === 1) return 'Tier 1'
  if (tier === 2) return 'Tier 2'
  return 'Untiered'
}

export function tierHotLabel(tier?: number): string {
  return tier === 1 ? 'Hot topic' : 'Lead story'
}

export function tierBadgeClass(tier?: number): string {
  return tier === 1 ? 'text-corridor-alert' : 'text-corridor-muted'
}

export function primaryTheme(article?: NewsArticle): string {
  const raw = article?.nlp_themes?.split(',')[0]?.trim()
  return raw || 'Geopolitical'
}

export function parseThemes(article?: NewsArticle): string[] {
  if (!article?.nlp_themes?.trim()) return []
  return article.nlp_themes
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
}

export function freshnessLabel(published?: string, scraped?: string): string {
  const value = published || scraped
  if (!value) return 'Freshness unknown'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Freshness unknown'
  const hours = (Date.now() - d.getTime()) / 3_600_000
  if (hours < 1) return 'Published within the hour'
  if (hours < 24) return 'Published today'
  if (hours < 72) return 'Published in last 3 days'
  return 'Older headline'
}

export function trustTierExplanation(tier?: number): string {
  if (tier === 1) return 'Tier 1 — high-salience geopolitical signal in Forsyt ingestion.'
  if (tier === 2) return 'Tier 2 — secondary signal; useful context, lower immediate weight.'
  return 'Not yet tier-ranked — awaiting pipeline scoring.'
}

export function tagStatusLine(article?: NewsArticle): string {
  const themes = parseThemes(article)
  if (themes.length) return `${themes.length} NLP theme${themes.length === 1 ? '' : 's'} applied`
  return 'Awaiting NLP tags'
}

export function briefWhyLine(article: NewsArticle): string {
  const parts: string[] = []
  if (article.tier === 1) parts.push('Tier 1')
  const theme = primaryTheme(article)
  if (theme !== 'Geopolitical') parts.push(theme)
  return parts.length ? parts.join(' · ') : 'Recent tagged flow'
}

export function crossLinkHints(
  article?: NewsArticle,
  corridorFilter?: string,
): { macro?: boolean; corridor?: boolean } {
  const themes = parseThemes(article).map((t) => t.toUpperCase())
  const macro =
    article?.tier === 1 ||
    themes.some((t) => ['CONFLICT', 'MILITARY', 'TERROR'].includes(t))
  const corridor =
    Boolean(corridorFilter) ||
    themes.some((t) => ['TRADE', 'CONFLICT', 'MILITARY'].includes(t))
  return { macro, corridor }
}
