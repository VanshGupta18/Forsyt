type Props = {
  feedCount: number
  tierOneCount: number
  taggedPct: number
  gprIndex: number | null
  topTheme: string
  totalIndexed: number | null
  loading?: boolean
}

function PulseCard({
  label,
  value,
  valueClass = 'text-white',
  sub,
}: {
  label: string
  value: string
  valueClass?: string
  sub?: string
}) {
  return (
    <div className="corridor-panel shrink-0 min-w-[140px] p-3 flex flex-col gap-1">
      <span className="corridor-kicker">{label}</span>
      <span className={`corridor-score text-2xl ${valueClass}`}>{value}</span>
      {sub && <span className="text-[10px] text-corridor-muted">{sub}</span>}
    </div>
  )
}

export default function NewsIntelStrip({
  feedCount,
  tierOneCount,
  taggedPct,
  gprIndex,
  topTheme,
  totalIndexed,
  loading,
}: Props) {
  return (
    <div className="news-pulse-track flex gap-2 pb-1 overflow-x-auto">
      <PulseCard label="In feed" value={loading ? '…' : String(feedCount)} />
      <PulseCard
        label="Tier 1"
        value={loading ? '…' : String(tierOneCount)}
        valueClass="text-corridor-alert"
      />
      <PulseCard
        label="Tagged"
        value={loading ? '…' : `${taggedPct}%`}
        sub="NLP coverage in feed"
      />
      <PulseCard
        label="Forsyt GPR"
        value={gprIndex != null ? String(gprIndex) : '—'}
        valueClass="text-corridor-watch"
      />
      <PulseCard label="Top theme" value={topTheme} sub="Dominant in feed" />
      <PulseCard
        label="Indexed"
        value={totalIndexed != null ? totalIndexed.toLocaleString() : '—'}
        sub="Total articles"
      />
    </div>
  )
}
