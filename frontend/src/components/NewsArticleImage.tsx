import { useArticleImage } from '../lib/useArticleImage'

export type NewsArticleImageVariant = 'thumb' | 'featured' | 'card' | 'hero' | 'ticker'

const VARIANT_CLASS: Record<NewsArticleImageVariant, string> = {
  thumb: 'w-[72px] aspect-[4/3] shrink-0',
  featured: 'w-[88px] aspect-[4/3] shrink-0',
  card: 'w-[72px] aspect-[4/3] shrink-0',
  hero: 'absolute inset-0',
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
  variant = 'thumb',
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
