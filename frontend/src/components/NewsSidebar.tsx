import { formatArticleTime, type NewsArticle } from '../lib/api'
import {
  briefWhyLine,
  newsBreakingEmptyLine,
  NEWS_TOP_STORIES_TITLE,
} from '../lib/newsCopy'

type Props = {
  topStories: NewsArticle[]
}

export default function NewsSidebar({ topStories }: Props) {
  return (
    <aside className="flex flex-col min-h-[280px] md:min-h-[340px] lg:border-r-2 lg:border-[#ff3333]/40 lg:pr-1">
      <div className="corridor-panel p-4 flex flex-col flex-1 min-h-0 overflow-hidden">
        <h2 className="corridor-kicker text-corridor-alert mb-3 shrink-0">{NEWS_TOP_STORIES_TITLE}</h2>
        <ul className="flex-1 min-h-0 overflow-y-auto news-stories-scroll pr-1">
          {topStories.slice(0, 6).map((article, i) => (
            <li
              key={article.link ?? `${article.title}-${i}`}
              className="border-b border-white/5 last:border-0 py-2.5 first:pt-0"
            >
              {article.link ? (
                <a
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-left w-full group no-underline text-inherit"
                >
                  <span className="corridor-headline text-sm lg:text-base group-hover:text-corridor-watch line-clamp-2">
                    {article.title}
                  </span>
                  <span className="block text-[10px] text-corridor-muted mt-1">
                    {briefWhyLine(article)} · {formatArticleTime(article.published_at || article.scraped_at)}
                  </span>
                </a>
              ) : (
                <div className="text-left w-full">
                  <span className="corridor-headline text-sm lg:text-base line-clamp-2">{article.title}</span>
                  <span className="block text-[10px] text-corridor-muted mt-1">
                    {briefWhyLine(article)} · {formatArticleTime(article.published_at || article.scraped_at)}
                  </span>
                </div>
              )}
            </li>
          ))}
          {!topStories.length && (
            <li className="text-sm text-corridor-muted">{newsBreakingEmptyLine()}</li>
          )}
        </ul>
      </div>
    </aside>
  )
}
