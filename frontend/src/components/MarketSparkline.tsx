// ---------------------------------------------------------------------------
// MarketSparkline draws a market price history (e.g. NIFTY 50) as a filled
// line chart on a plain <canvas>, using the same shared drawing helpers as
// GprHistoryChart.tsx — see lib/chartCanvas.ts's top-of-file comment for how
// the setupCanvas → plotSeries → draw... pipeline works and why no charting
// library is used. This component's specific job: filter the price history
// down to the selected period (1 month / 3 months / 6 months / 1 year),
// color the line green or red depending on whether the price went up or
// down over that window, and show a hover tooltip with the exact
// date/price under the mouse.
// ---------------------------------------------------------------------------
import { useEffect, useRef, useState } from 'react'
import type { MarketHistoryPayload } from '../lib/api'
import { formatPrice } from '../lib/api'
import {
  CHART_PALETTE,
  DEFAULT_PADDING,
  drawArea,
  drawCrosshair,
  drawGrid,
  drawXLabels,
  formatDateLong,
  formatDateShort,
  nearestIndex,
  pctChange,
  plotSeries,
  setupCanvas,
  yAxisTicks,
} from '../lib/chartCanvas'

const PERIOD_DAYS: Record<string, number> = {
  '1mo': 31,
  '3mo': 92,
  '6mo': 183,
  '1y': 366,
}

function filterByPeriod(points: Array<{ date: string; close: number }>, period: string) {
  if (!points.length) return points
  const days = PERIOD_DAYS[period] ?? PERIOD_DAYS['3mo']
  const last = points[points.length - 1]?.date
  if (!last) return points
  const end = new Date(`${last}T00:00:00`)
  if (Number.isNaN(end.getTime())) return points
  const start = new Date(end)
  start.setDate(start.getDate() - days)
  const startIso = start.toISOString().slice(0, 10)
  return points.filter((p) => p.date >= startIso)
}

type Props = {
  data: MarketHistoryPayload | null | undefined
  period?: string
  height?: number
  title?: string
  className?: string
  variant?: 'default' | 'corridor'
}

export default function MarketSparkline({
  data,
  period = '3mo',
  height = 280,
  title,
  className = '',
  variant = 'default',
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const points = filterByPeriod(data?.points ?? [], period)
  const closes = points.map((p) => p.close)
  const first = closes[0]
  const last = closes[closes.length - 1]
  const high = closes.length ? Math.max(...closes) : null
  const low = closes.length ? Math.min(...closes) : null
  const change = first != null && last != null ? pctChange(first, last) : null
  const up = (change ?? 0) >= 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !points.length) return

    const render = () => {
      const setup = setupCanvas(canvas, height)
      if (!setup) return
      const { ctx, width } = setup
      const pad = DEFAULT_PADDING

      ctx.clearRect(0, 0, width, height)

      const yMin = Math.min(...closes) * 0.998
      const yMax = Math.max(...closes) * 1.002
      const yTicks = yAxisTicks(yMin, yMax, 4)
      drawGrid(ctx, width, height, pad, yTicks, yMin, yMax)

      const plotted = plotSeries(closes, width, height, pad, yMin, yMax)
      const baselineY = pad.top + (height - pad.top - pad.bottom)
      const stroke = up ? CHART_PALETTE.niftyUp : CHART_PALETTE.niftyDown
      const fillTop = up ? CHART_PALETTE.niftyUpFill : CHART_PALETTE.niftyDownFill
      const fillBottom = up ? 'rgba(0, 200, 83, 0.02)' : 'rgba(255, 51, 51, 0.02)'

      drawArea(ctx, plotted, baselineY, stroke, fillTop, fillBottom, 2.5)
      drawXLabels(
        ctx,
        points.map((p) => formatDateShort(p.date)),
        plotted,
        height,
        pad,
      )

      if (hoverIndex != null && plotted[hoverIndex]) {
        drawCrosshair(ctx, plotted[hoverIndex].x, height, pad, up ? 'rgba(52, 211, 153, 0.4)' : 'rgba(248, 113, 113, 0.4)')
        ctx.save()
        ctx.beginPath()
        ctx.arc(plotted[hoverIndex].x, plotted[hoverIndex].y, 4, 0, Math.PI * 2)
        ctx.fillStyle = '#fff'
        ctx.fill()
        ctx.lineWidth = 2
        ctx.strokeStyle = stroke
        ctx.stroke()
        ctx.restore()
      }

      ctx.save()
      ctx.fillStyle = CHART_PALETTE.white
      ctx.font = '600 13px Inter, sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText(title ?? `NIFTY · ${period}`, pad.left, 18)
      ctx.restore()
    }

    render()
    const observer = new ResizeObserver(render)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [data, height, hoverIndex, points, closes, up, period, title])

  const onMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !points.length) return
    const rect = canvas.getBoundingClientRect()
    const x = event.clientX - rect.left
    const plotted = plotSeries(closes, rect.width, height, DEFAULT_PADDING, 0, 1)
    setHoverIndex(nearestIndex(x, plotted))
  }

  const hoverPoint = hoverIndex != null ? points[hoverIndex] : points[points.length - 1]
  const isCorridor = variant === 'corridor'

  if (!data) {
    return <p className="text-xs text-corridor-muted">Market history unavailable</p>
  }

  return (
    <div className={className}>
      {!isCorridor && points.length > 0 && (
        <div className="flex flex-wrap gap-5 mb-3 text-xs">
          <div>
            <span className="text-gray-500 uppercase tracking-wide">Last</span>
            <div className="text-white font-semibold text-lg">{formatPrice(last ?? 0)}</div>
          </div>
          {change != null && (
            <div>
              <span className="text-gray-500 uppercase tracking-wide">Period</span>
              <div className={up ? 'text-[#10B981] font-medium' : 'text-[#EF4444] font-medium'}>
                {up ? '+' : ''}{change.toFixed(2)}%
              </div>
            </div>
          )}
          {high != null && low != null && (
            <div>
              <span className="text-gray-500 uppercase tracking-wide">High / Low</span>
              <div className="text-gray-300 font-medium">{formatPrice(high)} / {formatPrice(low)}</div>
            </div>
          )}
          <div>
            <span className="text-gray-500 uppercase tracking-wide">Bars</span>
            <div className="text-gray-300 font-medium">{points.length} sessions</div>
          </div>
        </div>
      )}

      <div
        className={`relative w-full overflow-hidden ${
          isCorridor ? 'macro-chart-shell' : 'rounded-lg border border-white/5 bg-[#0A101C]/50'
        }`}
        style={{ height }}
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {!points.length && (
          <div className="flex items-center justify-center h-full text-sm text-gray-500">No market history</div>
        )}
        {points.length > 0 && (
          <>
            <canvas ref={canvasRef} className="w-full h-full" />
            {hoverPoint && hoverIndex != null && (
              <div className="pointer-events-none absolute top-3 right-3 rounded-md border border-white/10 bg-[#111827]/95 px-3 py-2 text-xs shadow-lg">
                <div className="text-gray-400">{formatDateLong(hoverPoint.date)}</div>
                <div className="text-white font-semibold mt-0.5">{formatPrice(hoverPoint.close)}</div>
              </div>
            )}
          </>
        )}
      </div>

      {data.stale && <p className="text-[10px] text-[#f59e0b] mt-2">Cached / stale data</p>}
    </div>
  )
}
