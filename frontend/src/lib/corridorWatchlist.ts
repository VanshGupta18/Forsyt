import { readJson, writeJson } from './storage'

const STORAGE_KEY = 'forsyt_corridor_watchlist'

export function loadWatchlist(): string[] {
  const parsed = readJson<unknown>(STORAGE_KEY, [])
  return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : []
}

export function saveWatchlist(ids: string[]): void {
  writeJson(STORAGE_KEY, [...new Set(ids)])
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
