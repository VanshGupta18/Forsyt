import { Link } from 'react-router-dom'
import { formatPrice, type MarketHistoryPayload, type MarketQuote } from '../lib/api'
import { changeClass } from '../lib/macroCopy'
import MicroSparkline from './MicroSparkline'

type StatProps = {
  variant?: 'stat'
  label: string
  value: string
  valueClass?: string
  href?: string
  className?: string
  valueSize?: 'lg' | '2xl'
}

type MarketProps = {
  variant: 'market'
  quote?: MarketQuote
  loading?: boolean
  selected?: boolean
  compact?: boolean
  history?: MarketHistoryPayload
  className?: string
}

type Props = StatProps | MarketProps

export default function PulseCard(props: Props) {
  if (props.variant === 'market') {
    const { quote, loading, selected, compact, history, className = '' } = props
    const label = quote?.label ?? '—'

    return (
      <div
        className={`corridor-panel shrink-0 p-3 flex flex-col gap-2 ${
          compact ? 'w-[140px]' : 'w-[168px]'
        } ${selected ? 'macro-pulse-card-selected' : ''} ${className}`}
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
        <div className={`corridor-score text-white ${compact ? 'text-lg' : 'text-xl'}`}>
          {loading ? '…' : quote ? formatPrice(quote.price, quote.currency) : '—'}
        </div>
        {!compact && history?.points?.length ? (
          <MicroSparkline height={40} points={history.points} />
        ) : null}
        <div className="text-[10px] text-corridor-muted">
          {quote?.as_of ?? (loading ? 'Loading' : 'Unavailable')}
          {quote?.stale ? ' · stale' : ''}
        </div>
      </div>
    )
  }

  const { label, value, valueClass = 'text-white', href, className = '', valueSize = '2xl' } = props
  const valueSizeClass = valueSize === 'lg' ? 'text-lg leading-snug line-clamp-2' : 'text-2xl'
  const panelClass = `corridor-panel shrink-0 min-w-[140px] p-3 flex flex-col gap-1 ${className}`

  const inner = (
    <>
      <span className="corridor-kicker">{label}</span>
      <span className={`corridor-score ${valueSizeClass} ${valueClass}`}>{value}</span>
    </>
  )

  if (href) {
    return (
      <Link to={href} className={`${panelClass} hover:bg-white/5 transition-colors`}>
        {inner}
      </Link>
    )
  }

  return <div className={panelClass}>{inner}</div>
}
