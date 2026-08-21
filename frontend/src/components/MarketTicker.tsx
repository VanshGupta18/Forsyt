// Simple horizontal row of market quotes (price + %change), shown at the top
// of the Portfolio page. Not to be confused with CorridorNewsTicker
// (headlines) or AppChrome's marquee ticker (auto-scrolling).
import { formatPrice, type MarketQuote } from '../lib/api'

type Props = {
  quotes: MarketQuote[]
  loading?: boolean
}

function changeClass(pct: number): string {
  if (pct > 0) return 'text-[#10B981]'
  if (pct < 0) return 'text-[#EF4444]'
  return 'text-gray-400'
}

export default function MarketTicker({ quotes, loading }: Props) {
  if (loading) {
    return (
      <div className="border-b border-white/5 bg-[#0A101C]/50 py-2">
        <div className="max-w-[1600px] mx-auto px-6 text-xs text-gray-500">Loading market quotes…</div>
      </div>
    )
  }

  if (!quotes.length) {
    return (
      <div className="border-b border-white/5 bg-[#0A101C]/50 py-2">
        <div className="max-w-[1600px] mx-auto px-6 text-xs text-gray-500">Market quotes unavailable</div>
      </div>
    )
  }

  return (
    <div className="border-b border-white/5 bg-[#0A101C]/50 py-2 overflow-x-auto scrollbar-hide">
      <div className="max-w-[1600px] mx-auto px-6 flex items-center gap-8 text-xs font-medium whitespace-nowrap">
        {quotes.map((q) => (
          <div key={q.key} className="flex items-center gap-2">
            <span className="text-gray-500">{q.label}:</span>
            <span className="text-white">{formatPrice(q.price, q.currency)}</span>
            <span className={changeClass(q.change_pct)}>
              ({q.change >= 0 ? '+' : ''}{q.change_pct}%)
            </span>
            {q.stale && <span className="text-[10px] text-[#f59e0b]">stale</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
