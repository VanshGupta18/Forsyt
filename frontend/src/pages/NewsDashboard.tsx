// Route: "/news" (News Intelligence). Shows a filterable feed of tracked
// geopolitical headlines: a hero story + "top stories today" rail, a risk
// context chart, a filterable grid of all headlines, and a scrolling ticker
// at the bottom. Filters (theme/tier/corridor) are kept in the URL query
// string so a filtered view can be shared/bookmarked.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import ApiErrorBanner from '../components/ApiErrorBanner'
import CorridorNewsTicker from '../components/CorridorNewsTicker'
import LoadingSkeleton from '../components/LoadingSkeleton'
import NewsArticleCard from '../components/NewsArticleCard'
import NewsHero from '../components/NewsHero'
import NewsIntelStrip from '../components/NewsIntelStrip'
import NewsRiskPanel from '../components/NewsRiskPanel'
import NewsSidebar from '../components/NewsSidebar'
import NewsThemeNav from '../components/NewsThemeNav'
import {
  fetchEventsFeed,
  fetchPageNews,
  type GprCurrent,
  type NewsArticle,
} from '../lib/api'
import { queryKeys } from '../lib/queryClient'
import {
  NEWS_EYEBROW,
  NEWS_FEED_TITLE,
  NEWS_PAGE_DISCLAIMER,
  NEWS_PAGE_SUBTITLE,
  NEWS_PAGE_TITLE,
  NEWS_TICKER_TITLE,
  newsEmptyLine,
  newsStatusLine,
} from '../lib/newsCopy'
import { loadBriefPreferences } from '../lib/newsPrefs'
import {
  dominantTheme,
  feedAfterHero,
  pickHeroArticle,
  rankMorningBrief,
} from '../lib/newsUtils'

const NEWS_POLL_MS = 10 * 60 * 1000

export default function NewsDashboard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [gprIndex, setGprIndex] = useState<number | null>(null)
  const [gpr7ma, setGpr7ma] = useState<number | null>(null)
  const [gpr30ma, setGpr30ma] = useState<number | null>(null)
  const [gprDate, setGprDate] = useState<string | null>(null)
  const [theme, setTheme] = useState(() => searchParams.get('theme') ?? '')
  const [tier, setTier] = useState('')
  const [corridor, setCorridor] = useState(() => searchParams.get('corridor') ?? '')
  const [feedError, setFeedError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pipelineRunAt, setPipelineRunAt] = useState<string | null>(null)

  const hasFilters = Boolean(theme.trim() || tier || corridor.trim())

  const { data: bundle } = useQuery({
    queryKey: queryKeys.news(50),
    queryFn: () => fetchPageNews(50),
    refetchInterval: NEWS_POLL_MS,
    enabled: !hasFilters,
  })

  useEffect(() => {
    if (!bundle || hasFilters) return
    setArticles(bundle.events ?? [])
    setGprIndex(bundle.gpr_current?.gpr_index ?? null)
    setGpr7ma(bundle.gpr_current?.gpr_7ma ?? null)
    setGpr30ma(bundle.gpr_current?.gpr_30ma ?? null)
    setGprDate(bundle.gpr_current?.date ?? null)
    setPipelineRunAt(bundle.status?.last_pipeline_runs?.platform_refresh?.run_at ?? null)
    setLoading(false)
  }, [bundle, hasFilters])

  const syncUrl = useCallback(
    (nextTheme: string, nextCorridor: string) => {
      const params = new URLSearchParams()
      if (nextTheme.trim()) params.set('theme', nextTheme.trim())
      if (nextCorridor.trim()) params.set('corridor', nextCorridor.trim())
      setSearchParams(params, { replace: true })
    },
    [setSearchParams],
  )

  const loadFeed = useCallback(() => {
    if (!articles.length) setLoading(true)
    setFeedError(null)
    fetchEventsFeed({
      limit: 40,
      theme: theme.trim() || undefined,
      tier: tier || undefined,
      corridor: corridor.trim() || undefined,
      tagged_only: true,
    })
      .then((payload) => setArticles(payload.events ?? []))
      .catch((err: Error) => setFeedError(err.message))
      .finally(() => setLoading(false))
  }, [theme, tier, corridor, articles.length])

  useEffect(() => {
    if (!hasFilters) return
    loadFeed()
  }, [hasFilters, loadFeed])

  useEffect(() => {
    if (!hasFilters) return
    const id = window.setInterval(loadFeed, NEWS_POLL_MS)
    return () => window.clearInterval(id)
  }, [hasFilters, loadFeed])

  const applyGpr = (gpr: GprCurrent) => {
    setGprIndex(gpr.gpr_index ?? null)
    setGpr7ma(gpr.gpr_7ma ?? null)
    setGpr30ma(gpr.gpr_30ma ?? null)
    setGprDate(gpr.date ?? null)
  }

  const handleRefresh = () => {
    setRefreshing(true)
    if (hasFilters) {
      loadFeed()
    } else {
      setLoading(!articles.length)
      fetchPageNews(50)
        .then((payload) => {
          setArticles(payload.events ?? [])
          applyGpr(payload.gpr_current ?? {})
          setPipelineRunAt(payload.status?.last_pipeline_runs?.platform_refresh?.run_at ?? null)
        })
        .catch((err: Error) => setFeedError(err.message))
        .finally(() => setLoading(false))
    }
    setTimeout(() => setRefreshing(false), 600)
  }

  const hero = useMemo(() => pickHeroArticle(articles), [articles])
  const topStories = useMemo(() => {
    const prefs = loadBriefPreferences()
    const ranked = rankMorningBrief(articles, prefs, 8)
    if (!hero?.link) return ranked
    return ranked.filter((a) => a.link !== hero.link)
  }, [articles, hero?.link])
  const restFeed = useMemo(() => feedAfterHero(articles, hero), [articles, hero])

  const tierOneCount = articles.filter((a) => a.tier === 1).length
  const topTheme = dominantTheme(articles)

  const handleThemeChange = (next: string) => {
    setTheme(next)
    syncUrl(next, corridor)
  }

  const handleCorridorClear = () => {
    setCorridor('')
    syncUrl(theme, '')
  }

  return (
    <div className="news-page corridor-page max-w-container-max mx-auto px-margin-page space-y-4 pb-10">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
        <div className="space-y-2 max-w-2xl">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            {NEWS_EYEBROW}
          </span>
          <h1 className="corridor-display font-headline-lg text-headline-lg">{NEWS_PAGE_TITLE}</h1>
          <p className="font-body-lg text-body-lg text-corridor-muted">{NEWS_PAGE_SUBTITLE}</p>
          <p className="text-xs text-corridor-muted/80 max-w-xl">{NEWS_PAGE_DISCLAIMER}</p>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="corridor-btn text-xs px-3 py-1.5"
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <span className="font-label-md text-[11px] text-corridor-muted/70">
            {newsStatusLine(gprDate, pipelineRunAt)}
          </span>
        </div>
      </header>

      <div className="mt-2">
        <NewsThemeNav
          theme={theme}
          tier={tier}
          corridor={corridor}
          onThemeChange={handleThemeChange}
          onTierChange={setTier}
          onCorridorClear={handleCorridorClear}
        />
      </div>

      {feedError && <ApiErrorBanner message={`Feed: ${feedError}`} onRetry={loadFeed} />}

      <NewsIntelStrip
        feedCount={articles.length}
        tierOneCount={tierOneCount}
        gprIndex={gprIndex}
        topTheme={topTheme}
        loading={loading}
      />

      {loading && !articles.length ? (
        <LoadingSkeleton lines={8} />
      ) : (
        <>
          {hero && (
            <>
              <section className="grid grid-cols-1 lg:grid-cols-[1.65fr_1fr] gap-4 items-stretch">
                <NewsHero article={hero} />
                <NewsSidebar topStories={topStories} />
              </section>
              <NewsRiskPanel
                gprIndex={gprIndex}
                gprDate={gprDate}
                gpr7ma={gpr7ma}
                gpr30ma={gpr30ma}
                gprHistory={bundle?.gpr_history?.history ?? []}
              />
            </>
          )}

          <section>
            <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold mb-3">
              {NEWS_FEED_TITLE}
            </h2>

            {loading && <LoadingSkeleton lines={4} className="mb-4" />}

            {!loading && !articles.length && !feedError && (
              <p className="text-sm text-corridor-muted">{newsEmptyLine()}</p>
            )}

            {!loading && restFeed.length > 0 && (
              <div className="corridor-panel overflow-hidden max-h-[min(440px,55vh)] md:max-h-[480px] flex flex-col">
                <div className="flex-1 min-h-0 overflow-y-auto news-stories-scroll p-2">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {restFeed.map((article, i) => (
                      <NewsArticleCard
                        key={article.link ?? `${article.title}-${i}`}
                        article={article}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </section>
        </>
      )}

      <section>
        <h2 className="corridor-kicker text-[#333] normal-case tracking-wide text-sm font-bold mb-2 px-1">
          {NEWS_TICKER_TITLE}
        </h2>
        <div className="news-ticker-light py-2">
          <CorridorNewsTicker
            articles={articles.slice(0, 12)}
            loading={loading}
            emptyMessage={newsEmptyLine()}
            variant="light"
          />
        </div>
      </section>
    </div>
  )
}
