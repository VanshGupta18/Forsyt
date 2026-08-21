// A labeled horizontal progress bar (0-100) colored by risk tier — used for
// the corridor detail panel's threat/goods/energy scores.
import { businessTierClass, businessTierLabel } from '../lib/corridorCopy'

export default function ScoreBar({
  label,
  value,
  muted = false,
}: {
  label: string
  value: number
  muted?: boolean
}) {
  const tier = businessTierLabel(value)
  return (
    <div className={`flex items-center gap-2 text-xs ${muted ? 'opacity-40' : 'text-corridor-muted'}`}>
      <span className="w-28 shrink-0">{label}</span>
      <div className="h-1.5 flex-1 bg-white/10 overflow-hidden">
        <div
          className={`h-full ${value >= 50 ? 'bg-corridor-alert' : value >= 20 ? 'bg-corridor-watch' : 'bg-corridor-clear'}`}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
      <span className={`w-16 text-right shrink-0 ${businessTierClass(value)}`}>{tier}</span>
    </div>
  )
}
