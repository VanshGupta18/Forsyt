const STORAGE_KEY = 'forsyt_corridor_watchlist'

export function loadWatchlist(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : []
  } catch {
    return []
  }
}

export function saveWatchlist(ids: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...new Set(ids)]))
}

export function toggleWatchlist(id: string): string[] {
  const current = loadWatchlist()
  const next = current.includes(id) ? current.filter((v) => v !== id) : [...current, id]
  saveWatchlist(next)
  return next
}

export function isWatchlisted(id: string): boolean {
  return loadWatchlist().includes(id)
}
