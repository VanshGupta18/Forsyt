import type { ReactNode } from 'react'
import { formatArticleTime, type NewsArticle } from '../lib/api'
import { primaryTheme, priorityLabel } from '../lib/newsCopy'
import { useArticleImage } from '../lib/useArticleImage'

type Props = {
  article: NewsArticle
  variant?: 'featured' | 'standard'
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

export default function NewsArticleCard({ article, variant = 'standard' }: Props) {
  const { src } = useArticleImage(article.link)
  const theme = primaryTheme(article)

  if (variant === 'featured') {
    return (
      <StoryLink
        link={article.link}
        className="corridor-panel overflow-hidden cursor-pointer hover:bg-[#111111] transition-colors"
      >
        <div className="flex flex-col sm:flex-row">
          <div className="sm:w-2/5 shrink-0">
            {src ? (
              <img src={src} alt="" className="w-full h-40 sm:h-full min-h-[160px] object-cover" loading="lazy" />
            ) : (
              <div className="w-full h-40 sm:min-h-[160px] bg-[#0d0d0d] flex items-center justify-center">
                <span className="corridor-kicker">News</span>
              </div>
            )}
          </div>
          <div className="p-4 flex flex-col gap-2 flex-1">
            <div className="flex justify-between gap-2 text-[10px] uppercase">
              <span className={article.tier === 1 ? 'text-corridor-alert font-bold' : 'text-corridor-muted'}>
                {theme}
              </span>
              <span className="text-corridor-muted shrink-0">
                {formatArticleTime(article.published_at || article.scraped_at)}
              </span>
            </div>
            <h3 className="corridor-headline line-clamp-3">{article.title}</h3>
            <span className="text-[10px] text-corridor-muted mt-auto">
              {article.source ?? 'Source'} · {priorityLabel(article.tier)}
            </span>
          </div>
        </div>
      </StoryLink>
    )
  }

  return (
    <StoryLink
      link={article.link}
      className="corridor-panel overflow-hidden cursor-pointer hover:bg-[#111111] transition-colors flex flex-col"
    >
      {src ? (
        <img src={src} alt="" className="w-full h-36 object-cover" loading="lazy" />
      ) : (
        <div className="w-full h-36 bg-[#0d0d0d] flex items-center justify-center">
          <span className="corridor-kicker">News</span>
        </div>
      )}
      <div className="p-4 flex flex-col gap-2 flex-1">
        <div className="flex justify-between gap-2 text-[10px] uppercase">
          <span className={article.tier === 1 ? 'text-corridor-alert font-bold' : 'text-corridor-muted'}>
            {theme}
          </span>
          <span className="text-corridor-muted shrink-0">
            {formatArticleTime(article.published_at || article.scraped_at)}
          </span>
        </div>
        <h3 className="corridor-headline text-sm line-clamp-3">{article.title}</h3>
        <span className="text-[10px] text-corridor-muted mt-auto">
          {article.source ?? 'Source'} · {priorityLabel(article.tier)}
        </span>
      </div>
    </StoryLink>
  )
}
