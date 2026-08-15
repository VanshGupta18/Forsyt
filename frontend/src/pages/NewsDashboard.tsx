import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ApiErrorBanner from '../components/ApiErrorBanner'
import CorridorNewsTicker from '../components/CorridorNewsTicker'
import LoadingSkeleton from '../components/LoadingSkeleton'
import NewsArticleCard from '../components/NewsArticleCard'
import NewsArticleDrawer from '../components/NewsArticleDrawer'
import NewsHero from '../components/NewsHero'
import NewsIntelStrip from '../components/NewsIntelStrip'
import NewsMorningBrief from '../components/NewsMorningBrief'
import NewsSidebar from '../components/NewsSidebar'
import NewsThemeNav from '../components/NewsThemeNav'
import {
  fetchEventsFeed,
  fetchGprCurrent,
  fetchPlatformStatus,
  fetchStats,
  type NewsArticle,
} from '../lib/api'
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
import {
  loadBriefGeneratedAt,
  loadBriefPreferences,
  touchBriefGeneratedAt,
} from '../lib/newsPrefs'
import {
  dominantTheme,
  feedAfterHero,
  pickBreakingArticles,
  pickHeroArticle,
  rankMorningBrief,
} from '../lib/newsUtils'

const NEWS_POLL_MS = 10 * 60 * 1000

export default function NewsDashboard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [gprIndex, setGprIndex] = useState<number | null>(null)
  const [gprDate, setGprDate] = useState<string | null>(null)
  const [totalArticles, setTotalArticles] = useState<number | null>(null)
  const [theme, setTheme] = useState(() => searchParams.get('theme') ?? '')
  const [tier, setTier] = useState('')
  const [corridor, setCorridor] = useState(() => searchParams.get('corridor') ?? '')
  const [feedError, setFeedError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [drawerArticle, setDrawerArticle] = useState<NewsArticle | null>(null)
  const [briefGeneratedAt, setBriefGeneratedAt] = useState<string | null>(() => loadBriefGeneratedAt())
  const [briefCollapsed, setBriefCollapsed] = useState(false)
  const [pipelineRunAt, setPipelineRunAt] = useState<string | null>(null)

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
    setLoading(true)
    setFeedError(null)
    fetchEventsFeed({
      limit: 40,
      theme: theme.trim() || undefined,
      tier: tier || undefined,
      corridor: corridor.trim() || undefined,
    })
      .then((payload) => setArticles(payload.events ?? []))
      .catch((err: Error) => setFeedError(err.message))
      .finally(() => setLoading(false))
  }, [theme, tier, corridor])

  useEffect(() => {
    loadFeed()
  }, [loadFeed])

  useEffect(() => {
    const id = window.setInterval(loadFeed, NEWS_POLL_MS)
    return () => window.clearInterval(id)
  }, [loadFeed])

  useEffect(() => {
    fetchGprCurrent()
      .then((gpr) => {
        setGprIndex(gpr.gpr_index ?? null)
        setGprDate(gpr.date ?? null)
      })
      .catch(() => undefined)
    fetchStats()
      .then((s) => setTotalArticles(s.total_articles ?? null))
      .catch(() => undefined)
    if (!loadBriefGeneratedAt()) {
      setBriefGeneratedAt(touchBriefGeneratedAt())
    }
  }, [])

  useEffect(() => {
    const refreshStatus = () => {
      fetchPlatformStatus()
        .then((status) => {
          setPipelineRunAt(status.last_pipeline_runs?.platform_refresh?.run_at ?? null)
        })
        .catch(() => undefined)
    }
    refreshStatus()
    const id = window.setInterval(refreshStatus, NEWS_POLL_MS)
    return () => window.clearInterval(id)
  }, [])

  const hero = useMemo(() => pickHeroArticle(articles), [articles])
  const breaking = useMemo(() => pickBreakingArticles(articles, hero?.link), [articles, hero?.link])
  const restFeed = useMemo(() => feedAfterHero(articles, hero), [articles, hero])
  const featured = restFeed.slice(0, 2)
  const gridArticles = restFeed.slice(2)

  const tierOneCount = articles.filter((a) => a.tier === 1).length
  const taggedCount = articles.filter((a) => a.nlp_themes?.trim()).length
  const taggedPct = articles.length ? Math.round((taggedCount / articles.length) * 100) : 0
  const topTheme = dominantTheme(articles)

  const briefItems = useMemo(() => {
    const prefs = loadBriefPreferences()
    return rankMorningBrief(articles, prefs, 8)
  }, [articles, briefGeneratedAt])

  const handleRefresh = () => {
    setRefreshing(true)
    loadFeed()
    fetchGprCurrent()
      .then((gpr) => {
        setGprIndex(gpr.gpr_index ?? null)
        setGprDate(gpr.date ?? null)
      })
      .catch(() => undefined)
    setTimeout(() => setRefreshing(false), 600)
  }

  const handleThemeChange = (next: string) => {
    setTheme(next)
    syncUrl(next, corridor)
  }

  const handleCorridorClear = () => {
    setCorridor('')
    syncUrl(theme, '')
  }

  const handleRegenerateBrief = () => {
    setBriefGeneratedAt(touchBriefGeneratedAt())
  }

  return (
    <div className="news-page corridor-page max-w-container-max mx-auto px-margin-page space-y-4 pb-10">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
        <div className="space-y-2 max-w-2xl">
          <span
            className="eyebrow-badge"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.85)' }}
          >
            <span
              className="eyebrow-dot"
              style={{ background: '#ffffff', boxShadow: '0 0 8px 2px rgba(255,255,255,0.25)' }}
            />
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
        taggedPct={taggedPct}
        gprIndex={gprIndex}
        topTheme={topTheme}
        totalIndexed={totalArticles}
        loading={loading}
      />

      {loading && !articles.length ? (
        <LoadingSkeleton lines={8} />
      ) : (
        <>
          {hero && (
            <section className="grid grid-cols-1 lg:grid-cols-[1.65fr_1fr] gap-4 items-start">
              <NewsHero article={hero} onIntelDetails={setDrawerArticle} />
              <NewsSidebar
                breaking={breaking}
                gprIndex={gprIndex}
                gprDate={gprDate}
                onSelect={setDrawerArticle}
              />
            </section>
          )}

          <NewsMorningBrief
            items={briefItems}
            generatedAt={briefGeneratedAt}
            collapsed={briefCollapsed}
            onToggle={() => setBriefCollapsed((v) => !v)}
            onRegenerate={handleRegenerateBrief}
            onSelect={setDrawerArticle}
          />

          <section>
            <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold mb-3">
              {NEWS_FEED_TITLE}
            </h2>

            {loading && <LoadingSkeleton lines={4} className="mb-4" />}

            {!loading && !articles.length && !feedError && (
              <p className="text-sm text-corridor-muted">{newsEmptyLine()}</p>
            )}

            {!loading && featured.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                {featured.map((article, i) => (
                  <NewsArticleCard
                    key={article.link ?? `${article.title}-feat-${i}`}
                    article={article}
                    variant="featured"
                    onSelect={setDrawerArticle}
                  />
                ))}
              </div>
            )}

            {!loading && gridArticles.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {gridArticles.map((article, i) => (
                  <NewsArticleCard
                    key={article.link ?? `${article.title}-${i}`}
                    article={article}
                    onSelect={setDrawerArticle}
                  />
                ))}
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

      <NewsArticleDrawer
        article={drawerArticle}
        corridorFilter={corridor}
        onClose={() => setDrawerArticle(null)}
      />
    </div>
  )
}
