// Macro page panel showing the combined "joint stress" score as a circular
// gauge (a CSS conic-gradient ring, not a chart library), plus its two
// contributing percentile bars.
import type { DualSignalPayload } from '../lib/api'
import {
  SCORE_LABELS,
  stressRegimeClass,
  stressRegimeLabel,
} from '../lib/macroCopy'
import ScoreBar from './ScoreBar'

type Props = {
  dual: DualSignalPayload | null
  volUnavailable: boolean
}

export default function JointStressPanel({ dual, volUnavailable }: Props) {
  const joint = dual?.joint_stress
  const score = joint?.stress_score

  return (
    <div className="corridor-panel p-4 h-full flex flex-col gap-4">
      <div>
        <p className="corridor-kicker">{SCORE_LABELS.joint}</p>
        <h2 className="corridor-headline mt-1">Combined stress</h2>
      </div>

      <div className="flex flex-col items-center py-2">
        <div className="relative w-36 h-36 border-4 border-[#1a1a1a] flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{
              background: `conic-gradient(var(--corridor-accent-alert) ${score ?? 0}%, transparent 0)`,
              mask: 'radial-gradient(farthest-side, transparent calc(100% - 8px), #000 calc(100% - 7px))',
              WebkitMask: 'radial-gradient(farthest-side, transparent calc(100% - 8px), #000 calc(100% - 7px))',
            }}
          />
          <div className="text-center z-10">
            <div className="corridor-score text-4xl text-white">{score ?? '—'}</div>
            <div className={`text-xs font-semibold mt-1 uppercase ${stressRegimeClass(joint?.stress_regime)}`}>
              {stressRegimeLabel(joint?.stress_regime)}
            </div>
          </div>
        </div>
      </div>

      {joint?.geo_percentile != null && (
        <ScoreBar label={SCORE_LABELS.geoPct} value={joint.geo_percentile} />
      )}
      {joint?.vol_percentile != null && (
        <ScoreBar label={SCORE_LABELS.volPct} value={joint.vol_percentile} muted={volUnavailable} />
      )}
    </div>
  )
}
