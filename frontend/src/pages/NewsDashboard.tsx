import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ApiErrorBanner from '../components/ApiErrorBanner'
import CorridorNewsTicker from '../components/CorridorNewsTicker'
import LiveClock from '../components/LiveClock'
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
} from '../lib/newsCopy'
import {
  addSavedView,
  loadBriefGeneratedAt,
  loadBriefPreferences,
  loadSavedViews,
  removeSavedView,
  touchBriefGeneratedAt,
  type SavedNewsView,
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
  const [savedViews, setSavedViews] = useState<SavedNewsView[]>(() => loadSavedViews())
  const [briefGeneratedAt, setBriefGeneratedAt] = useState<string | null>(() => loadBriefGeneratedAt())
  const [briefCollapsed, setBriefCollapsed] = useState(false)

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
    return rankMorningBrief(articles, prefs, savedViews, 8)
  }, [articles, savedViews, briefGeneratedAt])

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

  const handleApplyView = (view: SavedNewsView) => {
    setTheme(view.theme)
    setTier(view.tier)
    setCorridor(view.corridor)
    syncUrl(view.theme, view.corridor)
  }

  const handleSaveView = (name: string) => {
    setSavedViews(addSavedView({ name, theme, tier, corridor }))
  }

  const handleRemoveView = (id: string) => {
    setSavedViews(removeSavedView(id))
  }

  const handleRegenerateBrief = () => {
    setBriefGeneratedAt(touchBriefGeneratedAt())
  }

  return (
    <div className="news-page corridor-page max-w-container-max mx-auto px-margin-page space-y-4 pb-12">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-2">
        <div className="space-y-2 max-w-2xl">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            {NEWS_EYEBROW}
          </span>
          <h1 className="corridor-display font-headline-lg text-headline-lg">{NEWS_PAGE_TITLE}</h1>
          <p className="text-sm text-corridor-muted">{NEWS_PAGE_SUBTITLE}</p>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <LiveClock className="font-label-md text-[10px] text-corridor-muted" />
          {gprDate && (
            <span className="text-[10px] text-corridor-muted">GPR as of {gprDate.slice(0, 10)}</span>
          )}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="corridor-btn px-4 py-2 text-sm"
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </header>

      <NewsThemeNav
        theme={theme}
        tier={tier}
        corridor={corridor}
        savedViews={savedViews}
        onThemeChange={handleThemeChange}
        onTierChange={setTier}
        onCorridorClear={handleCorridorClear}
        onApplyView={handleApplyView}
        onSaveView={handleSaveView}
        onRemoveView={handleRemoveView}
      />

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

      <p className="text-[10px] text-corridor-muted text-center pt-2">{NEWS_PAGE_DISCLAIMER}</p>

      <NewsArticleDrawer
        article={drawerArticle}
        corridorFilter={corridor}
        onClose={() => setDrawerArticle(null)}
      />
    </div>
  )
}
