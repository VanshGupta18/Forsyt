import { NEWS_MOST_COVERED_LABEL } from '../lib/newsCopy'

type Props = {
  feedCount: number
  tierOneCount: number
  gprIndex: number | null
  topTheme: string
  loading?: boolean
}

function PulseCard({
  label,
  value,
  valueClass = 'text-white',
}: {
  label: string
  value: string
  valueClass?: string
}) {
  return (
    <div className="corridor-panel shrink-0 min-w-[140px] p-3 flex flex-col gap-1">
      <span className="corridor-kicker">{label}</span>
      <span className={`corridor-score text-2xl ${valueClass}`}>{value}</span>
    </div>
  )
}

export default function NewsIntelStrip({
  feedCount,
  tierOneCount,
  gprIndex,
  topTheme,
  loading,
}: Props) {
  return (
    <div className="news-pulse-track flex gap-2 pb-1 overflow-x-auto">
      <PulseCard label="Showing now" value={loading ? '…' : String(feedCount)} />
      <PulseCard
        label="High priority"
        value={loading ? '…' : String(tierOneCount)}
        valueClass="text-corridor-alert"
      />
      <PulseCard
        label="News risk score"
        value={gprIndex != null ? String(gprIndex) : '—'}
        valueClass="text-corridor-watch"
      />
      <PulseCard label={NEWS_MOST_COVERED_LABEL} value={topTheme} />
    </div>
  )
}
