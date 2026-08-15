import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { fetchNewsImage, formatArticleTime, type NewsArticle } from '../lib/api'
import { whyIncludedLabel } from '../lib/macroCopy'

function faviconUrl(link?: string): string | null {
  if (!link) return null
  try {
    const host = new URL(link).hostname
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=128`
  } catch {
    return null
  }
}

function TickerItem({ article, variant }: { article: NewsArticle; variant: 'dark' | 'light' }) {
  const [img, setImg] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const link = article.link ?? ''

  useEffect(() => {
    if (!link) return
    let cancelled = false
    fetchNewsImage(link)
      .then((url) => {
        if (!cancelled) setImg(url)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [link])

  const thumb = !failed && (img || faviconUrl(link))
  const badge = whyIncludedLabel(article.why_included)
  const isLight = variant === 'light'
  const imageBg = isLight ? 'bg-[#e8e8e3]' : 'bg-[#0a0a0a]'
  const headlineClass = isLight
    ? 'news-ticker-light-headline hover:opacity-80 line-clamp-2'
    : 'corridor-headline hover:text-corridor-watch line-clamp-2'
  const metaClass = isLight
    ? 'text-[10px] uppercase text-[#555] truncate normal-case min-w-0'
    : 'corridor-kicker truncate normal-case tracking-normal min-w-0'

  return (
    <article className="flex flex-col shrink-0 w-[260px] gap-2.5 px-3">
      {thumb ? (
        <img
          src={thumb}
          alt=""
          width={260}
          height={168}
          loading="lazy"
          className={`w-full h-[168px] object-cover ${imageBg}`}
          onError={() => setFailed(true)}
        />
      ) : (
        <div className={`w-full h-[168px] ${imageBg} flex items-center justify-center`}>
          <span className={isLight ? 'text-[10px] uppercase text-[#555] font-bold' : 'corridor-kicker'}>News</span>
        </div>
      )}
      <a
        href={link || undefined}
        target="_blank"
        rel="noopener noreferrer"
        className={headlineClass}
      >
        {article.title}
      </a>
      <div className="flex items-center gap-2 min-w-0">
        {badge && (
          <span
            className={`text-[9px] uppercase font-semibold px-1.5 py-0.5 shrink-0 ${
              isLight ? 'bg-black/10 text-[#333]' : 'bg-white/10 text-corridor-watch'
            }`}
          >
            {badge}
          </span>
        )}
        <p className={metaClass}>
          {article.source?.toUpperCase()} · {formatArticleTime(article.published_at || article.scraped_at)}
        </p>
      </div>
    </article>
  )
}

function TickerStrip({ articles, variant }: { articles: NewsArticle[]; variant: 'dark' | 'light' }) {
  return (
    <div className="flex items-start shrink-0">
      {articles.map((article, i) => (
        <TickerItem key={`${article.link ?? article.title}-${i}`} article={article} variant={variant} />
      ))}
    </div>
  )
}

function PosterSkeleton() {
  return (
    <div className="flex gap-3 overflow-hidden py-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="shrink-0 w-[260px] px-3 space-y-2.5">
          <div className="h-[168px] bg-white/5 animate-pulse" />
          <div className="h-4 bg-white/5 animate-pulse" />
          <div className="h-3 w-2/3 bg-white/5 animate-pulse" />
        </div>
      ))}
    </div>
  )
}

type Props = {
  articles: NewsArticle[]
  loading?: boolean
  emptyMessage?: string
  variant?: 'dark' | 'light'
}

export default function CorridorNewsTicker({ articles, loading, emptyMessage, variant = 'dark' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stripRef = useRef<HTMLDivElement>(null)
  const [paused, setPaused] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [overflows, setOverflows] = useState(false)
  const scrollTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReducedMotion(mq.matches)
    const handler = () => setReducedMotion(mq.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const measureOverflow = useCallback(() => {
    const container = containerRef.current
    const strip = stripRef.current
    if (!container || !strip) return
    setOverflows(strip.scrollWidth > container.clientWidth + 2)
  }, [])

  useLayoutEffect(() => {
    measureOverflow()
    const container = containerRef.current
    if (!container) return
    const ro = new ResizeObserver(measureOverflow)
    ro.observe(container)
    window.addEventListener('resize', measureOverflow)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measureOverflow)
    }
  }, [articles, loading, measureOverflow])

  const pauseBriefly = useCallback(() => {
    if (!overflows) return
    setPaused(true)
    if (scrollTimeout.current) clearTimeout(scrollTimeout.current)
    scrollTimeout.current = setTimeout(() => setPaused(false), 3000)
  }, [overflows])

  useEffect(() => {
    return () => {
      if (scrollTimeout.current) clearTimeout(scrollTimeout.current)
    }
  }, [])

  const isLight = variant === 'light'

  if (loading) {
    return <PosterSkeleton />
  }

  if (!articles.length) {
    return (
      <p className={`text-sm py-3 ${isLight ? 'text-[#555]' : 'text-corridor-muted'}`}>
        {emptyMessage ?? 'No recent news for this route yet.'}
      </p>
    )
  }

  const shouldAnimate = overflows && !reducedMotion

  return (
    <div
      ref={containerRef}
      className={`${overflows ? 'corridor-ticker-track' : 'overflow-hidden'} ${isLight ? 'news-ticker-light' : ''}`}
      onScroll={pauseBriefly}
      onPointerDown={() => overflows && setPaused(true)}
      onPointerUp={pauseBriefly}
      onMouseEnter={() => overflows && setPaused(true)}
      onMouseLeave={() => overflows && setPaused(false)}
    >
      <div
        className={`flex py-4 ${shouldAnimate ? 'w-max animate-marquee-slow' : ''} ${paused ? 'is-paused' : ''}`}
      >
        <div ref={stripRef}>
          <TickerStrip articles={articles} variant={variant} />
        </div>
        {shouldAnimate && <TickerStrip articles={articles} variant={variant} />}
      </div>
    </div>
  )
}
