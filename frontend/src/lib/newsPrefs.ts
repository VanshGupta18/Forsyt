import { readJson, writeJson } from './storage'

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

export function loadBriefPreferences(): BriefPreferences {
  return readJson(BRIEF_KEY, DEFAULT_BRIEF)
}

export function saveBriefPreferences(prefs: BriefPreferences): void {
  writeJson(BRIEF_KEY, prefs)
}
