import { formatArticleTime, type NewsArticle } from '../lib/api'
import {
  primaryTheme,
  tierBadgeClass,
  tierHotLabel,
} from '../lib/newsCopy'
import { useArticleImage } from '../lib/useArticleImage'

type Props = {
  article: NewsArticle
}

export default function NewsHero({ article }: Props) {
  const { src } = useArticleImage(article.link)
  const theme = primaryTheme(article)
  const isHot = article.tier === 1

  return (
    <article className="corridor-panel relative overflow-hidden min-h-[320px] md:min-h-[420px] flex flex-col justify-end">
      {src ? (
        <img
          src={src}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          loading="eager"
        />
      ) : (
        <div className="absolute inset-0 bg-[#111111]" />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/75 to-black/20" />

      <div className="relative p-5 md:p-8 space-y-3">
        <div className="flex items-center gap-2">
          {isHot && <span className="w-2 h-2 rounded-full bg-corridor-alert shrink-0" />}
          <span className={`corridor-kicker ${tierBadgeClass(article.tier)}`}>
            {tierHotLabel(article.tier)}
          </span>
        </div>

        <h2 className="news-hero-headline text-2xl md:text-4xl leading-tight max-w-3xl">
          {article.title}
        </h2>

        <p className="text-sm text-corridor-muted">
          <span className={isHot ? 'text-corridor-alert font-semibold' : ''}>{theme}</span>
          {' · '}
          {article.source ?? 'Source'}
          {' · '}
          {formatArticleTime(article.published_at || article.scraped_at)}
        </p>

        {article.link && (
          <div className="pt-1">
            <a
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="corridor-btn px-4 py-2 text-sm"
            >
              Open story
            </a>
          </div>
        )}
      </div>
    </article>
  )
}
