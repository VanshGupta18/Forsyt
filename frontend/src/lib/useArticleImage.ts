import { useCallback, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchNewsImage } from './api'
import { queryKeys } from './queryClient'

// Article thumbnails are resolved one link at a time by GET /api/news/image.
// A news feed renders dozens of cards at once, and the same article can also
// appear in the hero and the corridor ticker, so this used to fire one bare
// fetch per card per render with no sharing between them. Routing it through
// react-query means identical links de-duplicate into a single in-flight
// request and stay cached across re-renders and page navigations.
//
// The backend pre-resolves images in the hourly refresh, but only for a
// bounded batch (list_articles_missing_image(limit=20)), so anything beyond
// that backlog — and anything scraped since the last run — still lands here.
const IMAGE_STALE_MS = 6 * 60 * 60_000 // mirrors link_preview.py's ~6h cache

function isUsableImageUrl(url: string): boolean {
  try {
    const lower = url.toLowerCase()
    if (lower.endsWith('.ico') || lower.includes('favicon') || lower.includes('/icon.')) return false
    if (lower.includes('google.com/s2/favicons')) return false
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function useArticleImage(link?: string, imageUrl?: string | null): {
  src: string | null
  failed: boolean
  onImageError: () => void
} {
  // An image already attached to the article row needs no lookup at all.
  const direct = imageUrl && isUsableImageUrl(imageUrl) ? imageUrl : null
  const shouldLookup = !direct && Boolean(link)

  const { data, isError, isFetched } = useQuery({
    queryKey: queryKeys.newsImage(link ?? ''),
    queryFn: () => fetchNewsImage(link as string),
    enabled: shouldLookup,
    staleTime: IMAGE_STALE_MS,
    // A missing thumbnail is cosmetic — don't spend a retry on it.
    retry: false,
  })

  // Tracks the <img> tag itself failing to load a URL we believed was fine
  // (dead link, hotlink protection). Reset when the article changes.
  const [imgBroken, setImgBroken] = useState(false)
  useEffect(() => {
    setImgBroken(false)
  }, [link, imageUrl])

  const resolved = direct ?? (data && isUsableImageUrl(data) ? data : null)
  const failed = imgBroken || (shouldLookup && (isError || (isFetched && !resolved)))
  const onImageError = useCallback(() => setImgBroken(true), [])

  return { src: failed ? null : resolved, failed, onImageError }
}
