import {
  stressQuadrantId,
  todayVerdict,
  verdictToneClass,
  type TodayVerdictTone,
} from '../lib/macroCopy'

type Props = {
  geoPercentile?: number | null
  volPercentile?: number | null
  volUnavailable?: boolean
  stressRegime?: string | null
  loading?: boolean
}

function titleAccent(tone: TodayVerdictTone): string {
  if (tone === 'alert') return 'text-corridor-alert'
  if (tone === 'watch') return 'text-corridor-watch'
  if (tone === 'clear') return 'text-corridor-clear'
  return 'text-corridor-muted'
}

export default function TodayVerdict({
  geoPercentile,
  volPercentile,
  volUnavailable,
  stressRegime,
  loading,
}: Props) {
  if (loading) {
    return (
      <div className="corridor-panel border-l-4 border-white/20 p-4">
        <p className="corridor-kicker">Today&apos;s verdict</p>
        <p className="text-sm text-corridor-muted mt-1">Loading stress signals…</p>
      </div>
    )
  }

  const content = todayVerdict(geoPercentile, volPercentile, volUnavailable, stressRegime)
  const quadrant = stressQuadrantId(geoPercentile, volPercentile, volUnavailable)

  return (
    <div className={`corridor-panel border-l-4 p-4 ${verdictToneClass(content.tone)}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="corridor-kicker">Today&apos;s verdict</p>
        <span className="text-[10px] uppercase font-semibold text-corridor-muted tracking-wide">
          {quadrant === 'calm' && 'Calm'}
          {quadrant === 'geo' && 'Headline-led'}
          {quadrant === 'vol' && 'Market-led'}
          {quadrant === 'joint' && 'Aligned stress'}
        </span>
      </div>
      <h2 className={`corridor-headline mt-1 text-lg ${titleAccent(content.tone)}`}>{content.title}</h2>
      <p className="text-sm text-corridor-muted mt-2 leading-relaxed">{content.body}</p>
    </div>
  )
}
