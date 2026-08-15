import { formatArticleTime, type NewsArticle } from '../lib/api'
import {
  briefWhyLine,
  newsBreakingEmptyLine,
  NEWS_TOP_STORIES_TITLE,
} from '../lib/newsCopy'

type Props = {
  topStories: NewsArticle[]
  onSelect: (article: NewsArticle) => void
}

export default function NewsSidebar({ topStories, onSelect }: Props) {
  return (
    <aside className="corridor-panel p-4 flex flex-col min-h-[320px] md:min-h-[420px] lg:border-r-2 lg:border-[#ff3333]/40 overflow-hidden">
      <h2 className="corridor-kicker text-corridor-alert mb-3 shrink-0">{NEWS_TOP_STORIES_TITLE}</h2>
      <ul className="flex-1 min-h-0 overflow-y-auto news-stories-scroll pr-1">
        {topStories.slice(0, 6).map((article, i) => (
          <li
            key={article.link ?? `${article.title}-${i}`}
            className="border-b border-white/5 last:border-0 py-2.5 first:pt-0"
          >
            <button
              type="button"
              className="text-left w-full group"
              onClick={() => onSelect(article)}
            >
              <span className="corridor-headline text-sm lg:text-base group-hover:text-corridor-watch line-clamp-2">
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
    </aside>
  )
}
