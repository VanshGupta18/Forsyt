// Shared article-thumbnail box: resolves an image via useArticleImage and
// falls back to a plain "News" placeholder if none is available. Only the
// 'card' and 'ticker' variants are currently used by any component.
import { useArticleImage } from '../lib/useArticleImage'

export type NewsArticleImageVariant = 'card' | 'ticker'

const VARIANT_CLASS: Record<NewsArticleImageVariant, string> = {
  card: 'w-[72px] aspect-[4/3] shrink-0',
  ticker: 'w-full aspect-[16/10] shrink-0',
}

type Props = {
  link?: string
  imageUrl?: string | null
  variant?: NewsArticleImageVariant
  className?: string
  loading?: 'lazy' | 'eager'
}

export default function NewsArticleImage({
  link,
  imageUrl,
  variant = 'card',
  className = '',
  loading = 'lazy',
}: Props) {
  const { src, onImageError } = useArticleImage(link, imageUrl)
  const shellClass = `${VARIANT_CLASS[variant]} ${className}`.trim()

  return (
    <div className={`relative overflow-hidden bg-[#0d0d0d] ${shellClass}`}>
      {src ? (
        <img
          src={src}
          alt=""
          loading={loading}
          decoding="async"
          onError={onImageError}
          className="absolute inset-0 h-full w-full object-cover object-center"
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="corridor-kicker text-[10px]">News</span>
        </div>
      )}
    </div>
  )
}
