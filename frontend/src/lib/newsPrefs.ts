export type BriefPreferences = {
  themes: string[]
  minTier: number
  corridors: string[]
}

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
