import { Link } from 'react-router-dom'
import { formatArticleTime, type NewsArticle } from '../lib/api'
import {
  briefWhyLine,
  newsBreakingEmptyLine,
  NEWS_RISK_CONTEXT_TITLE,
  NEWS_TOP_STORIES_TITLE,
} from '../lib/newsCopy'
import GprHistoryChart from './GprHistoryChart'

type Props = {
  topStories: NewsArticle[]
  gprIndex: number | null
  gprDate: string | null
  onSelect: (article: NewsArticle) => void
}

export default function NewsSidebar({ topStories, gprIndex, gprDate, onSelect }: Props) {
  return (
    <aside className="space-y-4 lg:border-r-2 lg:border-[#ff3333]/40 lg:pr-1">
      <div className="corridor-panel p-4">
        <h2 className="corridor-kicker text-corridor-alert mb-3">{NEWS_TOP_STORIES_TITLE}</h2>
        <ul className="space-y-3">
          {topStories.map((article, i) => (
            <li key={article.link ?? `${article.title}-${i}`}>
              <button
                type="button"
                className="text-left w-full group"
                onClick={() => onSelect(article)}
              >
                <span className="corridor-headline text-sm group-hover:text-corridor-watch line-clamp-2">
                  {article.title}
                </span>
                <span className="block text-[10px] text-corridor-muted mt-1">
                  {briefWhyLine(article)} · {formatArticleTime(article.published_at || article.scraped_at)}
                </span>
              </button>
            </li>
          ))}
          {!topStories.length && (
            <li className="text-sm text-corridor-muted">{newsBreakingEmptyLine()}</li>
          )}
        </ul>
      </div>

      <div className="corridor-panel p-4 space-y-3">
        <h2 className="corridor-kicker">{NEWS_RISK_CONTEXT_TITLE}</h2>
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="corridor-kicker">News risk score</p>
            <span className="corridor-score text-3xl text-corridor-watch">
              {gprIndex ?? '—'}
            </span>
          </div>
          {gprDate && (
            <span className="text-[10px] text-corridor-muted">As of {gprDate.slice(0, 10)}</span>
          )}
        </div>
        <GprHistoryChart height={120} variant="corridor" period="3mo" compact className="mt-2" />
        <div className="flex flex-wrap gap-3 text-xs pt-1">
          <Link to="/macroeconomics" className="text-corridor-muted underline hover:text-white">
            Market stress monitor →
          </Link>
          <Link to="/trade-corridor" className="text-corridor-muted underline hover:text-white">
            Trade route risk →
          </Link>
        </div>
      </div>
    </aside>
  )
}
