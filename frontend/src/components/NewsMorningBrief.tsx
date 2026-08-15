import { formatArticleTime, type NewsArticle } from '../lib/api'
import { briefWhyLine, NEWS_MORNING_BRIEF_TITLE, primaryTheme } from '../lib/newsCopy'

type Props = {
  items: NewsArticle[]
  generatedAt: string | null
  collapsed: boolean
  onToggle: () => void
  onRegenerate: () => void
  onSelect: (article: NewsArticle) => void
}

export default function NewsMorningBrief({
  items,
  generatedAt,
  collapsed,
  onToggle,
  onRegenerate,
  onSelect,
}: Props) {
  return (
    <section className="corridor-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 p-4 border-b border-white/10">
        <div>
          <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold">
            {NEWS_MORNING_BRIEF_TITLE}
          </h2>
          {generatedAt && (
            <p className="text-[10px] text-corridor-muted mt-1">
              Generated {new Date(generatedAt).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button type="button" className="corridor-btn px-3 py-1.5 text-xs" onClick={onRegenerate}>
            Regenerate
          </button>
          <button type="button" className="corridor-btn px-3 py-1.5 text-xs" onClick={onToggle}>
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        </div>
      </div>

      {!collapsed && (
        <ul className="divide-y divide-white/5">
          {items.map((article, i) => (
            <li key={article.link ?? `${article.title}-${i}`}>
              <button
                type="button"
                className="w-full text-left px-4 py-3 hover:bg-[#111111] transition-colors"
                onClick={() => onSelect(article)}
              >
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span
                    className={`text-[9px] uppercase font-bold ${
                      article.tier === 1 ? 'text-corridor-alert' : 'text-corridor-muted'
                    }`}
                  >
                    {primaryTheme(article)}
                  </span>
                  <span className="text-[10px] text-corridor-muted">
                    {formatArticleTime(article.published_at || article.scraped_at)}
                  </span>
                </div>
                <p className="corridor-headline text-sm line-clamp-2">{article.title}</p>
                <p className="text-[10px] text-corridor-muted mt-1">{briefWhyLine(article)}</p>
              </button>
            </li>
          ))}
          {!items.length && (
            <li className="px-4 py-6 text-sm text-corridor-muted">No brief items for current filters.</li>
          )}
        </ul>
      )}
    </section>
  )
}
