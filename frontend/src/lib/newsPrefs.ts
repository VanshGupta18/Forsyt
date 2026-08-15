export type SavedNewsView = {
  id: string
  name: string
  theme: string
  tier: string
  corridor: string
  createdAt: string
}

export type BriefPreferences = {
  themes: string[]
  minTier: number
  corridors: string[]
}

const VIEWS_KEY = 'forsyt.news.savedViews'
const BRIEF_KEY = 'forsyt.news.briefPrefs'
const BRIEF_AT_KEY = 'forsyt.news.briefGeneratedAt'

const DEFAULT_BRIEF: BriefPreferences = {
  themes: [],
  minTier: 1,
  corridors: [],
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function loadSavedViews(): SavedNewsView[] {
  return readJson<SavedNewsView[]>(VIEWS_KEY, [])
}

export function saveSavedViews(views: SavedNewsView[]): void {
  localStorage.setItem(VIEWS_KEY, JSON.stringify(views))
}

export function addSavedView(view: Omit<SavedNewsView, 'id' | 'createdAt'>): SavedNewsView[] {
  const next: SavedNewsView = {
    ...view,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
  const views = [...loadSavedViews(), next]
  saveSavedViews(views)
  return views
}

export function removeSavedView(id: string): SavedNewsView[] {
  const views = loadSavedViews().filter((v) => v.id !== id)
  saveSavedViews(views)
  return views
}

export function loadBriefPreferences(): BriefPreferences {
  return readJson<BriefPreferences>(BRIEF_KEY, DEFAULT_BRIEF)
}

export function saveBriefPreferences(prefs: BriefPreferences): void {
  localStorage.setItem(BRIEF_KEY, JSON.stringify(prefs))
}

export function loadBriefGeneratedAt(): string | null {
  return localStorage.getItem(BRIEF_AT_KEY)
}

export function touchBriefGeneratedAt(): string {
  const iso = new Date().toISOString()
  localStorage.setItem(BRIEF_AT_KEY, iso)
  return iso
}

export function toggleBriefTheme(theme: string): BriefPreferences {
  const prefs = loadBriefPreferences()
  const upper = theme.toUpperCase()
  const themes = prefs.themes.includes(upper)
    ? prefs.themes.filter((t) => t !== upper)
    : [...prefs.themes, upper]
  const next = { ...prefs, themes }
  saveBriefPreferences(next)
  return next
}
