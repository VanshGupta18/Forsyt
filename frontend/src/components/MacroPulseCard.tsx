import { formatPrice, type MarketQuote } from '../lib/api'
import MicroSparkline from './MicroSparkline'

type Props = {
  quote?: MarketQuote
  loading?: boolean
  selected?: boolean
}

function changeClass(pct: number): string {
  if (pct > 0) return 'text-corridor-clear'
  if (pct < 0) return 'text-corridor-alert'
  return 'text-corridor-muted'
}

export default function MacroPulseCard({ quote, loading, selected }: Props) {
  const label = quote?.label ?? '—'
  const key = quote?.key ?? 'nifty'

  return (
    <div
      className={`corridor-panel shrink-0 w-[168px] p-3 flex flex-col gap-2 ${
        selected ? 'macro-pulse-card-selected' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-1">
        <span className="corridor-kicker truncate">{label}</span>
        {quote && (
          <span className={`text-[10px] font-semibold tabular-nums shrink-0 ${changeClass(quote.change_pct)}`}>
            {quote.change_pct >= 0 ? '+' : ''}
            {quote.change_pct}%
          </span>
        )}
      </div>
      <div className="corridor-score text-xl text-white">
        {loading ? '…' : quote ? formatPrice(quote.price, quote.currency) : '—'}
      </div>
      <MicroSparkline symbol={key} period="1mo" height={40} />
      <div className="text-[10px] text-corridor-muted">
        {quote?.as_of ?? (loading ? 'Loading' : 'Unavailable')}
        {quote?.stale ? ' · stale' : ''}
      </div>
    </div>
  )
}
