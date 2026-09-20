// Expanded, interactive view of one holding's GPR-vs-price overlay — opened by
// clicking a HoldingTile sparkline. Two independently-scaled lines (GPR + the
// stock's price) with a hover crosshair and a date/value tooltip. Closes on
// backdrop click, the ✕ button, or Escape.
import { useEffect, useRef, useState } from 'react'
import type { PortfolioHolding } from '../lib/api'
import { formatDateLong, formatDateShort } from '../lib/chartCanvas'

const W = 820
const H = 380
const PAD = { top: 24, right: 20, bottom: 34, left: 20 }

function jointColor(band: string): string {
  if (band === 'High stress') return '#ff3333'
  if (band === 'Watch') return '#f5b800'
  return '#00c853'
}

export default function HoldingChartModal({
  holding,
  onClose,
}: {
  holding: PortfolioHolding
  onClose: () => void
}) {
  const o = holding.overlay
  const series = o?.series ?? []
  const wrapRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const n = series.length
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (n <= 1 ? 0 : (i / (n - 1)) * plotW)

  // Each line keeps its own y-scale — GPR and a rebased price live on very
  // different ranges, so a shared axis would flatten one of them.
  const makeScale = (vals: number[]) => {
    const mn = Math.min(...vals)
    const range = Math.max(...vals) - mn || 1
    return (v: number) => PAD.top + plotH - ((v - mn) / range) * plotH
  }
  const yGpr = series.length ? makeScale(series.map((p) => p.gpr)) : () => 0
  const yPx = series.length ? makeScale(series.map((p) => p.px)) : () => 0
  const priceUp = (o?.price_change_pct ?? 0) >= 0
  const priceColor = priceUp ? '#38bdf8' : '#ff6b6b'

  const line = (key: 'gpr' | 'px') =>
    series.map((p, i) => `${x(i)},${(key === 'gpr' ? yGpr : yPx)(p[key])}`).join(' ')

  // ~5 evenly spaced date labels along the x-axis.
  const tickIdx = n <= 1 ? [0] : [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (n - 1)))

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (n < 1) return
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W // to viewBox units
    const i = Math.round(((px - PAD.left) / plotW) * (n - 1))
    setHover(Math.max(0, Math.min(n - 1, i)))
  }

  const hp = hover != null ? series[hover] : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${holding.ticker} chart`}
    >
      <div
        className="relative w-full max-w-4xl bg-[#0a0a0a] border border-white/10 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-white">{holding.ticker}</h2>
              {o && (
                <span
                  className="text-[9px] uppercase font-semibold px-1.5 py-0.5 rounded"
                  style={{ color: jointColor(o.joint_band), background: `${jointColor(o.joint_band)}1f` }}
                >
                  {o.joint_band}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500">{holding.sector}</p>
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

        <div ref={wrapRef} className="relative">
          {series.length < 2 ? (
            <div className="flex items-center justify-center text-sm text-gray-500" style={{ height: 240 }}>
              No overlay series for this holding.
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
                <polyline fill="none" stroke="#f5b800" strokeOpacity={0.85} strokeWidth={1.75} points={line('gpr')} />
                <polyline fill="none" stroke={priceColor} strokeWidth={2} points={line('px')} />

                {tickIdx.map((i) => (
                  <text key={i} x={x(i)} y={H - 12} fontSize={11} fill="#6b7280" textAnchor="middle">
                    {formatDateShort(series[i].d)}
                  </text>
                ))}

                {hover != null && hp && (
                  <>
                    <line x1={x(hover)} y1={PAD.top} x2={x(hover)} y2={PAD.top + plotH} stroke="#ffffff" strokeOpacity={0.25} strokeWidth={1} />
                    <circle cx={x(hover)} cy={yGpr(hp.gpr)} r={4} fill="#f5b800" stroke="#000" strokeWidth={1} />
                    <circle cx={x(hover)} cy={yPx(hp.px)} r={4} fill={priceColor} stroke="#000" strokeWidth={1} />
                  </>
                )}
              </svg>

              {hover != null && hp && (
                <div className="pointer-events-none absolute top-2 right-2 rounded-md border border-white/10 bg-[#111827]/95 px-3 py-2 text-xs shadow-lg">
                  <div className="text-gray-400">{formatDateLong(hp.d)}</div>
                  <div className="text-[#f5b800] font-semibold mt-0.5">GPR {hp.gpr.toFixed(1)}</div>
                  <div style={{ color: priceColor }}>Price {hp.px.toFixed(1)}</div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-corridor-muted">
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 inline-block" style={{ background: '#f5b800' }} /> GPR (rebased 100)</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 inline-block" style={{ background: priceColor }} /> Price (rebased 100)</span>
          {o && (
            <span className="ml-auto flex items-center gap-4 font-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
              <span>Joint <span style={{ color: jointColor(o.joint_band) }}>{o.joint_stress}</span></span>
              <span>Δ price <span style={{ color: priceUp ? '#38bdf8' : '#ff6b6b' }}>{o.price_change_pct >= 0 ? '+' : ''}{o.price_change_pct}%</span></span>
              <span>ρ GPR {o.corr ?? '—'}</span>
              <span>vol pctile {o.vol_percentile}</span>
              <span>wt {Math.round(holding.weight * 100)}%</span>
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
