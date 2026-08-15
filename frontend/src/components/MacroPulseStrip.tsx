import { MARKET_SYMBOL_ORDER, orderMarketQuotes, type MarketQuote } from '../lib/api'
import MacroPulseCard from './MacroPulseCard'

type Props = {
  quotes: MarketQuote[]
  loading?: boolean
}

export default function MacroPulseStrip({ quotes, loading }: Props) {
  const ordered = orderMarketQuotes(quotes)

  return (
    <div className="macro-pulse-track flex gap-2 pb-1">
      {MARKET_SYMBOL_ORDER.map((key) => {
        const quote = ordered.find((q) => q.key === key)
        return (
          <MacroPulseCard
            key={key}
            quote={quote}
            loading={loading}
            selected={key === 'nifty'}
          />
        )
      })}
    </div>
  )
}
