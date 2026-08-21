// One headline card in the News page's grid: thumbnail + topic badge + title
// + source/time. Renders as a clickable link if the article has a URL,
// otherwise as plain non-clickable content.
import type { ReactNode } from 'react'
import { formatArticleTime, type NewsArticle } from '../lib/api'
import { articleTopicLabel } from '../lib/newsCopy'
import NewsArticleImage from './NewsArticleImage'

type Props = {
  article: NewsArticle
}

function StoryLink({
  link,
  className,
  children,
}: {
  link?: string
  className: string
  children: ReactNode
}) {
  if (link) {
    return (
      <a
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        className={`${className} block no-underline text-inherit`}
      >
        {children}
      </a>
    )
  }
  return <article className={className}>{children}</article>
}

export default function NewsArticleCard({ article }: Props) {
  const topic = articleTopicLabel(article)
  const isHot = article.tier === 1

  return (
    <StoryLink
      link={article.link}
      className="corridor-panel overflow-hidden cursor-pointer hover:bg-[#111111] transition-colors flex flex-row h-full group"
    >
      {isHot && <span className="w-0.5 shrink-0 bg-corridor-alert" aria-hidden />}
      <div className="flex flex-row gap-2.5 p-2.5 flex-1 min-w-0">
        <NewsArticleImage link={article.link} imageUrl={article.image_url} variant="card" />
        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] uppercase">
            {isHot && <span className="w-1.5 h-1.5 rounded-full bg-corridor-alert shrink-0" aria-hidden />}
            <span className={isHot ? 'text-corridor-alert font-bold' : 'text-corridor-muted'}>{topic}</span>
            <span className="text-corridor-muted/40 hidden sm:inline">·</span>
            <span className="text-corridor-muted hidden sm:inline">
              {formatArticleTime(article.published_at || article.scraped_at)}
            </span>
          </div>
          <h3 className="corridor-headline text-sm line-clamp-2 group-hover:text-corridor-watch">{article.title}</h3>
          <span className="text-[10px] text-corridor-muted truncate">
            {article.source ?? 'Source'}
            <span className="sm:hidden"> · {formatArticleTime(article.published_at || article.scraped_at)}</span>
          </span>
        </div>
      </div>
    </StoryLink>
  )
}
