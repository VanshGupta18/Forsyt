import { NEWS_THEME_PRESETS } from '../lib/newsCopy'
import NewsSavedViews from './NewsSavedViews'
import type { SavedNewsView } from '../lib/newsPrefs'

type Props = {
  theme: string
  tier: string
  corridor: string
  savedViews: SavedNewsView[]
  onThemeChange: (theme: string) => void
  onTierChange: (tier: string) => void
  onCorridorClear: () => void
  onApplyView: (view: SavedNewsView) => void
  onSaveView: (name: string) => void
  onRemoveView: (id: string) => void
}

export default function NewsThemeNav({
  theme,
  tier,
  corridor,
  savedViews,
  onThemeChange,
  onTierChange,
  onCorridorClear,
  onApplyView,
  onSaveView,
  onRemoveView,
}: Props) {
  return (
    <section aria-label="Filters" className="space-y-3">
      <div className="flex flex-wrap items-center gap-1 border-b border-white/10 pb-2">
        <button
          type="button"
          className="corridor-tab px-2.5 py-1.5"
          data-active={!theme}
          onClick={() => onThemeChange('')}
        >
          All
        </button>
        {NEWS_THEME_PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            className="corridor-tab px-2.5 py-1.5"
            data-active={theme.toUpperCase() === preset}
            onClick={() => onThemeChange(preset)}
          >
            {preset}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {['', '1', '2'].map((t) => (
          <button
            key={t || 'all-tier'}
            type="button"
            className="corridor-tab px-2.5 py-1.5"
            data-active={tier === t}
            onClick={() => onTierChange(t)}
          >
            {t ? `Tier ${t}` : 'All tiers'}
          </button>
        ))}

        {corridor && (
          <span className="inline-flex items-center gap-2 px-2 py-1 bg-[#111111] text-xs text-white">
            <span className="corridor-kicker normal-case tracking-normal text-corridor-watch">
              Corridor: {corridor}
            </span>
            <button
              type="button"
              className="text-corridor-muted hover:text-white"
              aria-label="Clear corridor filter"
              onClick={onCorridorClear}
            >
              ×
            </button>
          </span>
        )}

        <NewsSavedViews
          savedViews={savedViews}
          onApply={onApplyView}
          onSave={onSaveView}
          onRemove={onRemoveView}
        />
      </div>
    </section>
  )
}
