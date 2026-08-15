import type { NewsArticle } from './api'
import { articleTopicLabel } from './newsCopy'
import type { BriefPreferences } from './newsPrefs'

function articleTime(article: NewsArticle): number {
  const raw = article.published_at || article.scraped_at
  if (!raw) return 0
  const t = new Date(raw).getTime()
  return Number.isNaN(t) ? 0 : t
}

export function pickHeroArticle(articles: NewsArticle[]): NewsArticle | null {
  if (!articles.length) return null
  return (
    articles.find((a) => a.tier === 1) ??
    articles.find((a) => a.nlp_themes?.trim()) ??
    articles[0]
  )
}

export function feedAfterHero(articles: NewsArticle[], hero: NewsArticle | null): NewsArticle[] {
  if (!hero?.link) return articles.slice(1)
  return articles.filter((a) => a.link !== hero.link)
}

export function dominantTheme(articles: NewsArticle[]): string {
  const counts = new Map<string, number>()
  for (const article of articles) {
    const topic = articleTopicLabel(article)
    if (topic === 'General') continue
    counts.set(topic, (counts.get(topic) ?? 0) + 1)
  }
  let best = '—'
  let max = 0
  for (const [theme, count] of counts) {
    if (count > max) {
      max = count
      best = theme
    }
  }
  return best
}

export function rankMorningBrief(
  articles: NewsArticle[],
  prefs: BriefPreferences,
  limit = 8,
): NewsArticle[] {
  return [...articles]
    .map((article) => {
      let score = articleTime(article) / 1e12
      if (article.tier === 1) score += 100
      else if (article.tier === 2) score += 40
      if (article.nlp_themes?.trim()) score += 20

      const themes = (article.nlp_themes ?? '').toUpperCase()
      if (prefs.themes.some((t) => themes.includes(t))) score += 30
      if (article.tier != null && article.tier <= prefs.minTier) score += 15

      return { article, score }
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(({ article }) => article)
}
