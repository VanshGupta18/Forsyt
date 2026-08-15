import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { fetchNewsImage, formatArticleTime, type NewsArticle } from '../lib/api'

function faviconUrl(link?: string): string | null {
  if (!link) return null
  try {
    const host = new URL(link).hostname
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=128`
  } catch {
    return null
  }
}

function TickerItem({ article }: { article: NewsArticle }) {
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

  return (
    <article className="flex flex-col shrink-0 w-[260px] gap-2.5 px-3">
      {thumb ? (
        <img
          src={thumb}
          alt=""
          width={260}
          height={168}
          loading="lazy"
          className="w-full h-[168px] object-cover bg-[#0a0a0a]"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="w-full h-[168px] bg-[#0a0a0a] flex items-center justify-center">
          <span className="corridor-kicker">News</span>
        </div>
      )}
      <a
        href={link || undefined}
        target="_blank"
        rel="noopener noreferrer"
        className="corridor-headline hover:text-corridor-watch line-clamp-2"
      >
        {article.title}
      </a>
      <p className="corridor-kicker truncate normal-case tracking-normal">
        {article.source?.toUpperCase()} · {formatArticleTime(article.published_at || article.scraped_at)}
      </p>
    </article>
  )
}

function TickerStrip({ articles }: { articles: NewsArticle[] }) {
  return (
    <div className="flex items-start shrink-0">
      {articles.map((article, i) => (
        <TickerItem key={`${article.link ?? article.title}-${i}`} article={article} />
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
}

export default function CorridorNewsTicker({ articles, loading, emptyMessage }: Props) {
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

  if (loading) {
    return <PosterSkeleton />
  }

  if (!articles.length) {
    return (
      <p className="text-sm text-corridor-muted py-3">
        {emptyMessage ?? 'No recent news for this route yet.'}
      </p>
    )
  }

  const shouldAnimate = overflows && !reducedMotion

  return (
    <div
      ref={containerRef}
      className={overflows ? 'corridor-ticker-track' : 'overflow-hidden'}
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
          <TickerStrip articles={articles} />
        </div>
        {shouldAnimate && <TickerStrip articles={articles} />}
      </div>
    </div>
  )
}
