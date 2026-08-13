import { useEffect, useState } from 'react'
import { fetchMarketQuotes, formatPrice, orderMarketQuotes, type MarketQuote } from '../lib/api'

function changeClass(pct: number): string {
  if (pct > 0) return 'text-secondary'
  if (pct < 0) return 'text-error'
  return 'text-on-surface-variant'
}

function Strip({ quotes }: { quotes: MarketQuote[] }) {
  return (
    <div className="flex items-center gap-6 pr-6 shrink-0" aria-hidden>
      {quotes.map((q, i) => (
        <span key={`${q.key}-${i}`} className="font-label-md whitespace-nowrap flex items-center gap-3">
          <span className="text-on-surface-variant">{q.label}</span>
          <span className="text-on-surface">{formatPrice(q.price, q.currency)}</span>
          <span className={changeClass(q.change_pct)}>
            {q.change_pct >= 0 ? '+' : ''}
            {q.change_pct}%
          </span>
          <span className="text-on-surface-variant/30">/////</span>
        </span>
      ))}
    </div>
  )
}

export default function HeroMarquee() {
  const [quotes, setQuotes] = useState<MarketQuote[]>([])

  useEffect(() => {
    fetchMarketQuotes()
      .then((payload) => setQuotes(orderMarketQuotes(payload.quotes ?? [])))
      .catch(() => undefined)
  }, [])

  if (!quotes.length) return null

  return (
    <div className="border-y border-white/5 bg-surface-container-lowest/60 py-3 overflow-hidden">
      <div className="flex w-max animate-marquee">
        <Strip quotes={quotes} />
        <Strip quotes={quotes} />
      </div>
    </div>
  )
}
