import { useCallback, useEffect, useState } from 'react'
import { fetchNewsImage } from './api'

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

export function useArticleImage(link?: string): {
  src: string | null
  failed: boolean
  onImageError: () => void
} {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!link) {
      setSrc(null)
      setFailed(false)
      return
    }

    let cancelled = false
    setSrc(null)
    setFailed(false)

    fetchNewsImage(link)
      .then((url) => {
        if (cancelled) return
        if (url && isUsableImageUrl(url)) setSrc(url)
        else setFailed(true)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })

    return () => {
      cancelled = true
    }
  }, [link])

  const onImageError = useCallback(() => {
    setFailed(true)
    setSrc(null)
  }, [])

  return { src: failed ? null : src, failed, onImageError }
}
