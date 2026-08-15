import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { formatArticleTime, type NewsArticle } from '../lib/api'
import {
  crossLinkHints,
  freshnessLabel,
  parseThemes,
  primaryTheme,
  tagStatusLine,
  tierLabel,
  trustTierExplanation,
} from '../lib/newsCopy'
import { toggleBriefTheme } from '../lib/newsPrefs'

type Props = {
  article: NewsArticle | null
  corridorFilter?: string
  onClose: () => void
}

export default function NewsArticleDrawer({ article, corridorFilter, onClose }: Props) {
  useEffect(() => {
    if (!article) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey)
    }
  }, [article, onClose])

  if (!article) return null

  const themes = parseThemes(article)
  const hints = crossLinkHints(article, corridorFilter)
  const theme = primaryTheme(article)

  const handlePinTheme = () => {
    if (theme !== 'Geopolitical') toggleBriefTheme(theme)
  }

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-black/60"
        aria-label="Close article details"
        onClick={onClose}
      />
      <aside
        className="fixed top-0 right-0 z-50 h-full w-full max-w-md corridor-panel overflow-y-auto shadow-2xl"
        role="dialog"
        aria-labelledby="news-drawer-title"
      >
        <div className="sticky top-0 bg-[#0a0a0a] border-b border-white/10 p-4 flex items-start justify-between gap-3">
          <div>
            <p className="corridor-kicker">Intel details</p>
            <h2 id="news-drawer-title" className="corridor-headline text-base mt-1 line-clamp-3">
              {article.title}
            </h2>
          </div>
          <button type="button" className="corridor-btn px-2 py-1 text-lg leading-none shrink-0" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex flex-wrap gap-2 text-xs">
            <span className={`px-2 py-1 bg-[#111111] ${article.tier === 1 ? 'text-corridor-alert' : 'text-corridor-muted'}`}>
              {tierLabel(article.tier)}
            </span>
            <span className="px-2 py-1 bg-[#111111] text-corridor-muted">{article.source ?? 'Source'}</span>
          </div>

          <p className="text-sm text-corridor-muted">
            {formatArticleTime(article.published_at || article.scraped_at)}
          </p>

          {article.link && (
            <a
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="corridor-btn inline-block px-4 py-2 text-sm"
            >
              Read original →
            </a>
          )}

          <div className="corridor-advisory p-3 space-y-2 border-l-2 border-corridor-watch">
            <p className="corridor-kicker">Trust</p>
            <p className="text-sm text-corridor-muted">{trustTierExplanation(article.tier)}</p>
            <p className="text-sm text-corridor-muted">{tagStatusLine(article)}</p>
            <p className="text-sm text-corridor-muted">
              {freshnessLabel(article.published_at, article.scraped_at)}
            </p>
          </div>

          {themes.length > 0 && (
            <div>
              <p className="corridor-kicker mb-2">NLP themes</p>
              <div className="flex flex-wrap gap-1.5">
                {themes.map((t) => (
                  <span key={t} className="text-[10px] px-2 py-1 bg-[#111111] text-corridor-muted uppercase">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(hints.macro || hints.corridor) && (
            <div>
              <p className="corridor-kicker mb-2">Related Forsyt modules</p>
              <div className="flex flex-wrap gap-3 text-sm">
                {hints.macro && (
                  <Link to="/macroeconomics" className="text-corridor-watch underline">
                    Market stress monitor
                  </Link>
                )}
                {hints.corridor && (
                  <Link
                    to={corridorFilter ? `/trade-corridor` : '/trade-corridor'}
                    className="text-corridor-watch underline"
                  >
                    Corridor risk
                  </Link>
                )}
              </div>
            </div>
          )}

          {theme !== 'Geopolitical' && (
            <button type="button" className="corridor-btn px-3 py-2 text-xs" onClick={handlePinTheme}>
              Pin “{theme}” to morning brief
            </button>
          )}
        </div>
      </aside>
    </>
  )
}
