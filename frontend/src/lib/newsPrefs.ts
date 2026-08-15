export type BriefPreferences = {
  themes: string[]
  minTier: number
  corridors: string[]
}

const BRIEF_KEY = 'forsyt.news.briefPrefs'

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
