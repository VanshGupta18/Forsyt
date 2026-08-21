// News page's filter bar: theme tabs (All/Conflict/Military/...), a
// high-priority-only toggle, and a "clear route filter" chip when a corridor
// filter is active. Purely controlled — all filter state lives in the parent page.
import { NEWS_THEME_PRESETS, themeDisplayLabel } from '../lib/newsCopy'

type Props = {
  theme: string
  tier: string
  corridor: string
  onThemeChange: (theme: string) => void
  onTierChange: (tier: string) => void
  onCorridorClear: () => void
}

export default function NewsThemeNav({
  theme,
  tier,
  corridor,
  onThemeChange,
  onTierChange,
  onCorridorClear,
}: Props) {
  return (
    <section aria-label="Filter headlines" className="flex flex-wrap items-center gap-2">
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
          {themeDisplayLabel(preset)}
        </button>
      ))}

      <span className="w-px h-3.5 bg-white/10" aria-hidden />

      <button
        type="button"
        className="corridor-tab px-2.5 py-1.5"
        data-active={!tier}
        onClick={() => onTierChange('')}
      >
        All stories
      </button>
      <button
        type="button"
        className="corridor-tab px-2.5 py-1.5"
        data-active={tier === '1'}
        onClick={() => onTierChange('1')}
      >
        High priority only
      </button>

      {corridor && (
        <>
          <span className="w-px h-3.5 bg-white/10" aria-hidden />
          <span className="inline-flex items-center gap-2 px-2 py-1 bg-[#111111] text-xs text-white">
            <span className="corridor-kicker normal-case tracking-normal text-corridor-watch">
              Route filter: {corridor}
            </span>
            <button
              type="button"
              className="text-corridor-muted hover:text-white"
              aria-label="Clear route filter"
              onClick={onCorridorClear}
            >
              ×
            </button>
          </span>
        </>
      )}
    </section>
  )
}
