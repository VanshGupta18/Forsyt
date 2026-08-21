// News page's row of quick-glance PulseCard stats: how many stories showing,
// how many high-priority, current news-risk score, and the most-covered topic.
import PulseCard from './PulseCard'
import { NEWS_MOST_COVERED_LABEL } from '../lib/newsCopy'

type Props = {
  feedCount: number
  tierOneCount: number
  gprIndex: number | null
  topTheme: string
  loading?: boolean
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
