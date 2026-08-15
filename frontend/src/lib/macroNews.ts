import { fetchEventsFeed, type NewsArticle } from './api'

/** Keywords for Indian market / macro stress relevance */
const MARKET_KEYWORDS = [
  'market',
  'nifty',
  'sensex',
  'stock',
  'rupee',
  'inr',
  'rbi',
  'inflation',
  'bse',
  'nse',
  'forex',
  'equity',
  'sebi',
  'gdp',
  'sanction',
  'crude',
  'oil',
  'vix',
  'bond',
  'yield',
  'fii',
  'dii',
  'trade',
  'economy',
  'monetary',
  'fiscal',
] as const

export function isMarketRelatedArticle(article: NewsArticle): boolean {
  const text = `${article.title ?? ''} ${article.nlp_themes ?? ''}`.toLowerCase()
  return MARKET_KEYWORDS.some((kw) => text.includes(kw))
}

export function mergeMacroHeadlines(
  driving: NewsArticle[] | undefined,
  feed: NewsArticle[],
  limit = 8,
): NewsArticle[] {
  const seen = new Set<string>()
  const out: NewsArticle[] = []

  for (const article of [...(driving ?? []), ...feed]) {
    const key = article.link ?? article.title ?? ''
    if (!key || seen.has(key)) continue
    seen.add(key)
    out.push(article)
    if (out.length >= limit) break
  }

  return out
}

export async function fetchMacroMarketNews(limit = 8): Promise<NewsArticle[]> {
  const res = await fetchEventsFeed({ limit: 60, tagged_only: true })
  const market = (res.events ?? []).filter(isMarketRelatedArticle)
  return market.slice(0, limit)
}
