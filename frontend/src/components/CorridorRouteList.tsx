// Horizontal scrollable strip of corridor "chip" buttons (below the map on
// the Corridor Risk page) — click one to select it, or the star to pin/unpin
// it on the user's watchlist.
import { corridorOperationalRisk, formatCorridorName, type CorridorRow } from '../lib/api'
import { businessTierClass, tierAccentColor } from '../lib/corridorCopy'
import { isWatchlisted } from '../lib/corridorWatchlist'

type Props = {
  rows: CorridorRow[]
  selected: string | null
  onSelect: (id: string) => void
  onToggleWatchlist: (id: string) => void
}

export default function CorridorRouteList({ rows, selected, onSelect, onToggleWatchlist }: Props) {
  if (!rows.length) {
    return <p className="text-sm text-corridor-muted py-2">No routes match these filters.</p>
  }

  return (
    <div className="mt-3">
      <h3 className="corridor-kicker mb-2">
        Routes <span className="font-normal tracking-normal">({rows.length})</span>
      </h3>
      <div className="flex gap-2 overflow-x-auto scrollbar-hide py-1 -mx-1 px-1">
        {rows.map((row) => {
          const key = row.corridor?.toLowerCase() ?? ''
          const stress = corridorOperationalRisk(row)
          const isActive = selected === key
          const pinned = isWatchlisted(key)

          return (
            <button
              key={key}
              type="button"
              onClick={() => onSelect(key)}
              className={`group shrink-0 flex items-center gap-1.5 max-w-[160px] px-3 py-1.5 rounded-full text-left text-xs transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--corridor-focus)] ${
                isActive ? 'text-white font-semibold' : 'text-corridor-muted hover:text-white/90 font-medium'
              }`}
              style={isActive ? { boxShadow: `inset 0 -2px 0 ${tierAccentColor(stress)}` } : undefined}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${businessTierClass(stress).replace('text-', 'bg-')}`}
                aria-hidden
              />
              <span className="truncate">{formatCorridorName(row.corridor, row.corridor_name)}</span>
              <span
                role="button"
                tabIndex={0}
                aria-label={pinned ? 'Remove from my routes' : 'Pin to my routes'}
                onClick={(e) => {
                  e.stopPropagation()
                  onToggleWatchlist(key)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    e.stopPropagation()
                    onToggleWatchlist(key)
                  }
                }}
                className={`shrink-0 text-[10px] leading-none opacity-0 group-hover:opacity-100 transition-opacity ${
                  pinned ? 'opacity-100 text-corridor-watch' : 'text-corridor-muted'
                }`}
              >
                {pinned ? '★' : '☆'}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
