import { SCORE_LABELS, STRESS_MAP_CORNERS, stressPositionAdvisory, stressQuadrantId } from '../lib/macroCopy'

type Props = {
  geoPercentile?: number | null
  volPercentile?: number | null
  volUnavailable?: boolean
}

export default function StressPositionMap({ geoPercentile, volPercentile, volUnavailable }: Props) {
  const geo = Math.max(0, Math.min(100, geoPercentile ?? 0))
  const vol = volUnavailable ? 0 : Math.max(0, Math.min(100, volPercentile ?? 0))
  const quadrant = stressQuadrantId(geoPercentile, volPercentile, volUnavailable)
  const advisory = stressPositionAdvisory(geoPercentile, volPercentile, volUnavailable)

  const dotColor =
    quadrant === 'joint'
      ? 'var(--corridor-accent-alert)'
      : quadrant === 'geo' || quadrant === 'vol'
        ? 'var(--corridor-accent-watch)'
        : 'var(--corridor-accent-clear)'

  return (
    <div className="corridor-panel p-4 h-full flex flex-col gap-3">
      <div>
        <p className="corridor-kicker">Stress map</p>
        <h2 className="corridor-headline mt-1">Where you sit today</h2>
      </div>

      <div className="relative flex-1 min-h-[200px] bg-[#0d0d0d] border border-white/10">
        {/* quadrant divider lines */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/15" aria-hidden />
        <div className="absolute top-1/2 left-0 right-0 h-px bg-white/15" aria-hidden />

        {/* corner labels */}
        <span className="absolute top-2 left-2 corridor-kicker text-[9px]">{STRESS_MAP_CORNERS.tl}</span>
        <span className="absolute top-2 right-2 corridor-kicker text-[9px]">{STRESS_MAP_CORNERS.tr}</span>
        <span className="absolute bottom-2 left-2 corridor-kicker text-[9px]">{STRESS_MAP_CORNERS.bl}</span>
        <span className="absolute bottom-2 right-2 corridor-kicker text-[9px]">{STRESS_MAP_CORNERS.br}</span>

        {/* axis hint */}
        <span className="absolute bottom-1 left-1/2 -translate-x-1/2 text-[9px] text-corridor-muted">
          News risk →
        </span>

        {/* position dot */}
        {!volUnavailable && (
          <div
            className="absolute z-10 flex flex-col items-center gap-1 pointer-events-none"
            style={{
              left: `${geo}%`,
              bottom: `${vol}%`,
              transform: 'translate(-50%, 50%)',
            }}
          >
            <div
              className="w-3 h-3 rounded-full border-2 border-white shadow-[0_0_8px_rgba(255,255,255,0.4)]"
              style={{ backgroundColor: dotColor }}
            />
            <span className="text-[9px] font-semibold text-white uppercase whitespace-nowrap bg-black/80 px-1">
              You are here
            </span>
          </div>
        )}

        {volUnavailable && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-corridor-muted px-4 text-center">
            Vol data unavailable — map shows geo only ({geo}%)
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3 text-[10px] text-corridor-muted">
        <span>{SCORE_LABELS.geoPct}: {geoPercentile ?? '—'}</span>
        <span>{SCORE_LABELS.volPct}: {volUnavailable ? 'N/A' : (volPercentile ?? '—')}</span>
      </div>

      <p className="text-xs text-corridor-muted leading-relaxed">{advisory}</p>
    </div>
  )
}
