import { useCallback, useEffect, useState } from 'react'
import {
  fetchEventsFeed,
  fetchGprCurrent,
  fetchStats,
  formatArticleTime,
  type NewsArticle,
} from '../lib/api'
import Reveal from '../components/Reveal'
import ApiErrorBanner from '../components/ApiErrorBanner'
import LiveClock from '../components/LiveClock'
import LoadingSkeleton from '../components/LoadingSkeleton'
import GprHistoryChart from '../components/GprHistoryChart'

const THEME_PRESETS = ['', 'CONFLICT', 'MILITARY', 'TRADE', 'TERROR'] as const

export default function NewsDashboard() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [gprIndex, setGprIndex] = useState<number | null>(null)
  const [gprDate, setGprDate] = useState<string | null>(null)
  const [totalArticles, setTotalArticles] = useState<number | null>(null)
  const [theme, setTheme] = useState('')
  const [tier, setTier] = useState<string>('')
  const [feedError, setFeedError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadFeed = useCallback(() => {
    setLoading(true)
    setFeedError(null)
    fetchEventsFeed({
      limit: 30,
      theme: theme.trim() || undefined,
      tier: tier || undefined,
    })
      .then((payload) => setArticles(payload.events ?? []))
      .catch((err: Error) => setFeedError(err.message))
      .finally(() => setLoading(false))
  }, [theme, tier])

  useEffect(() => {
    loadFeed()
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
  }, [])

  const tierOneCount = articles.filter((a) => a.tier === 1).length
  const taggedCount = articles.filter((a) => a.nlp_themes?.trim()).length

  return (
    <div className="flex-1 w-full max-w-[1400px] mx-auto px-6 py-6 flex flex-col gap-6">
      <Reveal className="pt-2 pb-1 space-y-2">
        <span className="eyebrow-badge">
          <span className="eyebrow-dot" />
          Live News Intelligence
        </span>
        <h1 className="text-2xl font-bold text-white">News Intelligence</h1>
        <p className="text-sm text-[#8b97ab] max-w-2xl">
          Geopolitical events from live PostgreSQL — filter by NLP theme or ingestion tier.
        </p>
      </Reveal>

      <section aria-label="Filters" className="flex flex-col gap-3 w-full">
        <div className="relative flex-1 md:max-w-md">
          <input
            className="block w-full pl-3 pr-3 py-2 bg-[#111520] border border-[#1f2638] rounded-lg text-sm text-[#e2e8f0] placeholder-[#8b97ab] focus:ring-1 focus:ring-[#3b82f6] outline-none"
            placeholder="Filter by theme (e.g. CONFLICT, TRADE)…"
            type="text"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadFeed()}
          />
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {['', '1', '2'].map((t) => (
            <button
              key={t || 'all'}
              type="button"
              onClick={() => setTier(t)}
              className={`px-3 py-2 rounded-lg text-sm border transition-colors ${
                tier === t
                  ? 'border-[#3b82f6] bg-[#3b82f6]/10 text-white'
                  : 'border-[#1f2638] text-[#8b97ab] hover:text-white'
              }`}
            >
              {t ? `Tier ${t}` : 'All tiers'}
            </button>
          ))}
          {THEME_PRESETS.filter(Boolean).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTheme(t)}
              className={`px-3 py-2 rounded-lg text-xs border transition-colors ${
                theme.toUpperCase() === t
                  ? 'border-[#f59e0b] bg-[#f59e0b]/10 text-white'
                  : 'border-[#1f2638] text-[#8b97ab] hover:text-white'
              }`}
            >
              {t}
            </button>
          ))}
          <button type="button" onClick={loadFeed} className="px-3 py-2 rounded-lg text-sm bg-[#3b82f6] text-white ml-auto">
            Refresh
          </button>
        </div>
      </section>

      {feedError && <ApiErrorBanner message={`Feed: ${feedError}`} onRetry={loadFeed} />}

      <Reveal>
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card-lift bg-[#111520] border border-[#2e4063] rounded-xl p-5">
            <span className="text-xs font-semibold text-[#8b97ab] uppercase">In feed</span>
            <span className="text-3xl font-bold text-white block mt-1">{loading ? '…' : articles.length}</span>
          </div>
          <div className="card-lift bg-[#111520] border border-[#4a2424] rounded-xl p-5">
            <span className="text-xs font-semibold text-[#8b97ab] uppercase">Tier-1 in feed</span>
            <span className="text-3xl font-bold text-[#ef4444] block mt-1">{loading ? '…' : tierOneCount}</span>
          </div>
          <div className="card-lift bg-[#111520] border border-[#1b3d31] rounded-xl p-5">
            <span className="text-xs font-semibold text-[#8b97ab] uppercase">Total indexed</span>
            <span className="text-3xl font-bold text-white block mt-1">{totalArticles ?? '—'}</span>
          </div>
          <div className="card-lift bg-[#111520] border border-[#2e4063] rounded-xl p-5">
            <span className="text-xs font-semibold text-[#8b97ab] uppercase">Forsyt GPR</span>
            <span className="text-3xl font-bold text-[#f59e0b] block mt-1">{gprIndex ?? '—'}</span>
            <span className="text-xs text-[#8b97ab]">{gprDate ? `As of ${gprDate}` : 'Live index'}</span>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="bg-[#111520] border border-[#1f2638] rounded-xl p-5">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
            <div>
              <h2 className="text-base font-semibold text-white">Forsyt GPR index</h2>
              <p className="text-xs text-[#8b97ab] mt-1">
                Daily geopolitical risk from tagged news — context for the feed below
                {gprDate ? ` · as of ${gprDate}` : ''}
              </p>
            </div>
            {gprIndex != null && (
              <div className="text-right">
                <span className="text-xs text-[#8b97ab] uppercase">Latest</span>
                <div className="text-2xl font-bold text-[#f59e0b] tabular-nums">{gprIndex}</div>
              </div>
            )}
          </div>
          <GprHistoryChart height={300} />
        </section>
      </Reveal>

      <Reveal>
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 bg-[#111520] border border-[#1f2638] rounded-xl p-5 flex flex-col max-h-[520px]">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#1f2638]/50">
              <h2 className="text-base font-semibold text-white">Latest headlines</h2>
              <LiveClock className="font-label-md text-[10px] text-[#8b97ab]" />
            </div>
            <div className="flex-1 overflow-y-auto space-y-3">
              {loading && <LoadingSkeleton lines={4} />}
              {!loading && articles.slice(0, 8).map((article, i) => (
                <div key={article.link ?? `${article.title}-${i}`} className="border border-[#1f2638] rounded-lg p-3">
                  <a href={article.link} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-white hover:text-[#3b82f6] line-clamp-2">
                    {article.title}
                  </a>
                  <p className="text-xs text-[#8b97ab] mt-1">{article.source} · tier {article.tier ?? '—'} · {formatArticleTime(article.published_at || article.scraped_at)}</p>
                </div>
              ))}
              {!articles.length && !loading && <p className="text-sm text-[#8b97ab]">No articles match filters.</p>}
            </div>
            {!loading && (
              <p className="text-[10px] text-[#8b97ab] mt-3 pt-3 border-t border-[#1f2638]">
                {taggedCount}/{articles.length} articles with NLP tags in this feed
              </p>
            )}
          </div>

          <div className="xl:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">News Intelligence Feed</h2>
            </div>
            {loading && <LoadingSkeleton lines={6} className="mb-4" />}
            {!loading && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {articles.map((article, i) => (
                  <article key={article.link ?? `${article.title}-${i}`} className="bg-[#111520] border border-[#1f2638] rounded-xl overflow-hidden flex flex-col">
                    <div className="p-5 flex-1 flex flex-col">
                      <div className="flex items-center justify-between text-xs text-[#8b97ab] uppercase mb-2 gap-2">
                        <span className="truncate">{article.nlp_themes?.split(',')[0]?.trim() || 'Geopolitical'}</span>
                        <span className="shrink-0">{formatArticleTime(article.published_at || article.scraped_at)}</span>
                      </div>
                      <h3 className="text-base font-semibold text-white leading-snug mb-4">
                        <a href={article.link} target="_blank" rel="noopener noreferrer" className="hover:text-[#3b82f6]">
                          {article.title}
                        </a>
                      </h3>
                      <span className="px-2 py-1 text-[10px] font-bold bg-[#0a0d14] text-[#8b97ab] border border-[#1f2638] rounded w-fit">
                        {article.source || 'Source'} · tier {article.tier ?? '—'}
                      </span>
                      <p className="text-xs text-[#8b97ab] mt-2 line-clamp-2">{article.nlp_themes || '(awaiting NLP tags)'}</p>
                    </div>
                  </article>
                ))}
              </div>
            )}
            {!loading && !articles.length && !feedError && (
              <p className="text-sm text-[#8b97ab]">Try clearing theme filters or run the NLP backfill pipeline.</p>
            )}
          </div>
        </section>
      </Reveal>
    </div>
  )
}
