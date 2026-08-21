// Macro page's row of live market-quote PulseCards, plus a "what changed"
// summary line and transmission-channel badges (oil-rupee / risk-off — see
// lib/macroCopy.ts's computeTransmission).
import { MARKET_SYMBOL_ORDER, orderMarketQuotes, type MarketHistoryPayload, type MarketQuote } from '../lib/api'
import {
  computeTransmission,
  transmissionToneClass,
  whatChangedLine,
} from '../lib/macroCopy'
import PulseCard from './PulseCard'

type Props = {
  quotes: MarketQuote[]
  loading?: boolean
  geoChange7d?: number | null
  indexDays?: number | null
  marketHistories?: Record<string, MarketHistoryPayload>
}

export default function MacroPulseStrip({
  quotes,
  loading,
  geoChange7d,
  indexDays,
  marketHistories,
}: Props) {
  const ordered = orderMarketQuotes(quotes)
  const transmission = computeTransmission(
    quotes.map((q) => ({ key: q.key, change_pct: q.change_pct })),
  )
  const changed = whatChangedLine(
    geoChange7d,
    indexDays,
    quotes.map((q) => ({ key: q.key, label: q.label, change_pct: q.change_pct })),
  )

  return (
    <div className="space-y-2">
      <div className="macro-pulse-track flex gap-2 pb-1">
        {MARKET_SYMBOL_ORDER.map((key) => {
          const quote = ordered.find((q) => q.key === key)
          return (
            <PulseCard
              key={key}
              variant="market"
              quote={quote}
              loading={loading}
              selected={key === 'nifty'}
              history={marketHistories?.[key]}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2 px-1">
        <span className={`text-[10px] font-semibold uppercase ${transmissionToneClass(transmission.tone)}`}>
          {loading ? 'Checking channels…' : transmission.label}
        </span>
        {transmission.channels.includes('oil_rupee') && (
          <span className="text-[9px] uppercase px-1.5 py-0.5 bg-white/5 text-corridor-watch">Oil–rupee</span>
        )}
        {transmission.channels.includes('risk_off') && (
          <span className="text-[9px] uppercase px-1.5 py-0.5 bg-white/5 text-corridor-watch">Risk-off</span>
        )}
      </div>
      <p className="text-[11px] text-corridor-muted/80 px-1">{changed}</p>
    </div>
  )
}
