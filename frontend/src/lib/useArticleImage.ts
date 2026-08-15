import { useEffect, useState } from 'react'
import { fetchNewsImage } from './api'

function faviconUrl(link?: string): string | null {
  if (!link) return null
  try {
    const host = new URL(link).hostname
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=128`
  } catch {
    return null
  }
}

export function useArticleImage(link?: string): { src: string | null; failed: boolean } {
  const [img, setImg] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!link) return
    let cancelled = false
    setImg(null)
    setFailed(false)
    fetchNewsImage(link)
      .then((url) => {
        if (!cancelled) setImg(url)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [link])

  const src = !failed && (img || faviconUrl(link)) ? img || faviconUrl(link) : null
  return { src, failed }
}
