// Expanded, interactive price chart for one market quote (NIFTY, SENSEX, oil,
// …) — opened by clicking its PulseCard on the Markets page. Single close-price
// line with a hover crosshair + date/price tooltip. Closes on backdrop, ✕, Esc.
import { useEffect, useState } from 'react'
import { formatPrice, type MarketHistoryPayload, type MarketQuote } from '../lib/api'
import { changeClass } from '../lib/macroCopy'
import { formatDateLong, formatDateShort } from '../lib/chartCanvas'

const W = 820
const H = 380
const PAD = { top: 24, right: 20, bottom: 34, left: 20 }

export default function MarketChartModal({
  quote,
  history,
  onClose,
}: {
  quote?: MarketQuote
  history?: MarketHistoryPayload
  onClose: () => void
}) {
  const points = history?.points ?? []
  const [hover, setHover] = useState<number | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const n = points.length
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (n <= 1 ? 0 : (i / (n - 1)) * plotW)

  const closes = points.map((p) => p.close)
  const mn = closes.length ? Math.min(...closes) : 0
  const range = (closes.length ? Math.max(...closes) : 1) - mn || 1
  const y = (v: number) => PAD.top + plotH - ((v - mn) / range) * plotH

  const up = (quote?.change_pct ?? 0) >= 0
  const lineColor = up ? '#00c853' : '#ff6b6b'
  const linePts = points.map((p, i) => `${x(i)},${y(p.close)}`).join(' ')
  const tickIdx = n <= 1 ? [0] : [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (n - 1)))

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (n < 1) return
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const i = Math.round(((px - PAD.left) / plotW) * (n - 1))
    setHover(Math.max(0, Math.min(n - 1, i)))
  }

  const hp = hover != null ? points[hover] : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${quote?.label ?? 'Market'} chart`}
    >
      <div
        className="relative w-full max-w-4xl bg-[#0a0a0a] border border-white/10 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <div className="flex items-baseline gap-3">
              <h2 className="text-lg font-semibold text-white">{quote?.label ?? '—'}</h2>
              {quote && (
                <>
                  <span className="text-lg text-white tabular-nums">{formatPrice(quote.price, quote.currency)}</span>
                  <span className={`text-sm tabular-nums ${changeClass(quote.change_pct)}`}>
                    {quote.change_pct >= 0 ? '+' : ''}{quote.change_pct}%
                  </span>
                </>
              )}
            </div>
            <p className="text-xs text-gray-500">
              {quote?.as_of ?? ''}{quote?.stale ? ' · stale' : ''}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-gray-400 hover:text-white text-xl leading-none px-2"
          >
            ✕
          </button>
        </div>

        <div className="relative">
          {n < 2 ? (
            <div className="flex items-center justify-center text-sm text-gray-500" style={{ height: 240 }}>
              No price history for this market.
            </div>
          ) : (
            <>
              <svg
                viewBox={`0 0 ${W} ${H}`}
                className="w-full"
                style={{ height: 'auto' }}
                onMouseMove={onMove}
                onMouseLeave={() => setHover(null)}
              >
                <polyline fill="none" stroke={lineColor} strokeWidth={2} points={linePts} />

                {tickIdx.map((i) => (
                  <text key={i} x={x(i)} y={H - 12} fontSize={11} fill="#6b7280" textAnchor="middle">
                    {formatDateShort(points[i].date)}
                  </text>
                ))}

                {hover != null && hp && (
                  <>
                    <line x1={x(hover)} y1={PAD.top} x2={x(hover)} y2={PAD.top + plotH} stroke="#ffffff" strokeOpacity={0.25} strokeWidth={1} />
                    <circle cx={x(hover)} cy={y(hp.close)} r={4} fill={lineColor} stroke="#000" strokeWidth={1} />
                  </>
                )}
              </svg>

              {hover != null && hp && (
                <div className="pointer-events-none absolute top-2 right-2 rounded-md border border-white/10 bg-[#111827]/95 px-3 py-2 text-xs shadow-lg">
                  <div className="text-gray-400">{formatDateLong(hp.date)}</div>
                  <div className="text-white font-semibold mt-0.5 tabular-nums">
                    {formatPrice(hp.close, quote?.currency)}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
