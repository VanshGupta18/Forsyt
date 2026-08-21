// ---------------------------------------------------------------------------
// GprHistoryChart draws the "News risk index" line chart with its 7-day and
// 30-day moving averages, using a plain HTML <canvas> — see the big comment
// at the top of lib/chartCanvas.ts for why there's no charting library here
// and how the drawing pipeline (setupCanvas → plotSeries → draw...) works.
// This component's own job on top of that shared pipeline is: filter the
// history to the selected time period, decide the chart's Y-axis min/max,
// draw the "baseline 100" reference line (only once there's enough history
// to make it meaningful), and drive a canvas repaint whenever the data,
// hover position, or size changes.
// ---------------------------------------------------------------------------
import { useEffect, useRef, useState } from 'react'
import type { GprHistoryPoint } from '../lib/api'
import {
  CHART_PALETTE,
  DEFAULT_PADDING,
  drawArea,
  drawCrosshair,
  drawGrid,
  drawHLine,
  drawMarker,
  drawSeriesWithGaps,
  drawXLabels,
  formatDateLong,
  formatDateShort,
  nearestIndex,
  plotSeries,
  setupCanvas,
  yAxisTicks,
} from '../lib/chartCanvas'

const EVENT_MARKERS = [
  { date: '2019-02-14', label: 'Pulwama' },
  { date: '2020-06-15', label: 'Galwan' },
  { date: '2025-05-07', label: 'May 2025' },
]

const CHART_HEIGHT = 360
const FILL_MIN_HEIGHT = 200

export type GprChartPeriod = '1mo' | '3mo' | '6mo' | '1y'

const PERIOD_DAYS: Record<GprChartPeriod, number> = {
  '1mo': 31,
  '3mo': 92,
  '6mo': 183,
  '1y': 366,
}

function filterByPeriod(history: GprHistoryPoint[], period?: GprChartPeriod): GprHistoryPoint[] {
  if (!period || !history.length) return history
  const last = history[history.length - 1]?.date
  if (!last) return history
  const end = new Date(last)
  if (Number.isNaN(end.getTime())) return history
  const start = new Date(end)
  start.setDate(start.getDate() - PERIOD_DAYS[period])
  const startIso = start.toISOString().slice(0, 10)
  return history.filter((d) => d.date >= startIso)
}

type Props = {
  height?: number
  className?: string
  variant?: 'default' | 'corridor'
  period?: GprChartPeriod
  compact?: boolean
  fill?: boolean
  history: GprHistoryPoint[]
  indexDays?: number | null
  onRangeNote?: (note: string | null) => void
}

function validPoints(history: GprHistoryPoint[]) {
  return history.filter((d) => Number.isFinite(Number(d.gpr_index)))
}

function seriesValues(history: GprHistoryPoint[], key: keyof GprHistoryPoint) {
  return history.map((d) => {
    const val = Number(d[key])
    return Number.isFinite(val) ? val : NaN
  })
}

// The actual paint routine, called from the `useEffect` below and again any
// time the canvas resizes (via ResizeObserver). It: sizes the canvas
// (setupCanvas), works out the Y-axis range across all visible series
// (`gprVals`/`ma7`/`ma30`, plus the value 100 if the "baseline" reference
// line should be shown), draws grid lines, fills the GPR line as a shaded
// area, overlays the moving-average lines, drops a vertical marker+label at
// a few notable historical dates (EVENT_MARKERS), and finally draws a
// hover crosshair + dot if the mouse is currently over the chart.
function drawGprChart(
  canvas: HTMLCanvasElement,
  history: GprHistoryPoint[],
  hoverIndex: number | null,
  height: number,
  indexDays?: number | null,
) {
  const setup = setupCanvas(canvas, height)
  if (!setup) return
  const { ctx, width } = setup
  const pad = DEFAULT_PADDING

  ctx.clearRect(0, 0, width, height)

  const rows = validPoints(history)
  if (!rows.length) {
    ctx.fillStyle = CHART_PALETTE.muted
    ctx.font = '14px Inter, sans-serif'
    ctx.fillText('No GPR history yet — run daily index / backfill pipeline', pad.left, 48)
    return
  }

  const gprVals = seriesValues(rows, 'gpr_index').filter(Number.isFinite)
  const ma7 = seriesValues(rows, 'gpr_7ma')
  const ma30 = seriesValues(rows, 'gpr_30ma')
  const hasMa7 = ma7.some(Number.isFinite)
  const hasMa30 = ma30.some(Number.isFinite)

  const showBaselineLine = indexDays == null || indexDays >= 30
  const allVals = [
    ...gprVals,
    ...(hasMa7 ? ma7.filter(Number.isFinite) : []),
    ...(hasMa30 ? ma30.filter(Number.isFinite) : []),
    ...(showBaselineLine ? [100] : []),
  ]
  const yMin = Math.min(...allVals) * 0.92
  const yMax = Math.max(...allVals) * 1.08
  const yTicks = yAxisTicks(yMin, yMax, 5)

  drawGrid(ctx, width, height, pad, yTicks, yMin, yMax)

  const labels = rows.map((d) => formatDateShort(d.date))
  const gprPoints = plotSeries(gprVals, width, height, pad, yMin, yMax)
  const baselineY = pad.top + (height - pad.top - pad.bottom)

  if (
    showBaselineLine &&
    gprVals.some((v) => v <= 100) &&
    gprVals.some((v) => v >= 100)
  ) {
    const refY =
      pad.top +
      (height - pad.top - pad.bottom) -
      ((100 - yMin) / (yMax - yMin || 1)) * (height - pad.top - pad.bottom)
    drawHLine(ctx, refY, width, pad, CHART_PALETTE.baseline)
    ctx.save()
    ctx.fillStyle = CHART_PALETTE.muted
    ctx.font = '10px Inter, sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText('baseline 100', pad.left + 4, refY - 6)
    ctx.restore()
  }

  drawArea(
    ctx,
    gprPoints,
    baselineY,
    CHART_PALETTE.gpr,
    CHART_PALETTE.gprFill,
    CHART_PALETTE.gprFillBottom,
    2.5,
  )

  if (hasMa30) {
    drawSeriesWithGaps(ctx, ma30, width, height, pad, yMin, yMax, CHART_PALETTE.ma30, 1.25, true)
  }

  if (hasMa7) {
    drawSeriesWithGaps(ctx, ma7, width, height, pad, yMin, yMax, CHART_PALETTE.ma7, 1.5)
  }

  const firstDate = rows[0].date
  const lastDate = rows[rows.length - 1].date
  EVENT_MARKERS.forEach((marker) => {
    if (marker.date < firstDate || marker.date > lastDate) return
    const idx = rows.findIndex((d) => d.date >= marker.date)
    if (idx < 0) return
    drawMarker(ctx, gprPoints[idx].x, height, pad, marker.label)
  })

  drawXLabels(ctx, labels, gprPoints, height, pad)

  if (hoverIndex != null && gprPoints[hoverIndex]) {
    drawCrosshair(ctx, gprPoints[hoverIndex].x, height, pad)
    ctx.save()
    ctx.beginPath()
    ctx.arc(gprPoints[hoverIndex].x, gprPoints[hoverIndex].y, 4, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = CHART_PALETTE.gpr
    ctx.stroke()
    ctx.restore()
  }

  ctx.save()
  ctx.fillStyle = CHART_PALETTE.white
  ctx.font = '600 13px Inter, sans-serif'
  ctx.textAlign = 'left'
  ctx.fillText('Forsyt GPR index', pad.left, 18)
  ctx.restore()
}

export default function GprHistoryChart({
  height = CHART_HEIGHT,
  className = '',
  variant = 'default',
  period,
  compact = false,
  fill = false,
  history,
  indexDays,
  onRangeNote,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const [fillHeight, setFillHeight] = useState(FILL_MIN_HEIGHT)

  const chartHeight = fill ? fillHeight : height

  const filtered = filterByPeriod(history, period)
  const rows = validPoints(filtered)
  const fullRows = validPoints(history)
  const latest = rows[rows.length - 1]
  const first = rows[0]
  const gprVals = rows.map((d) => Number(d.gpr_index))
  const minVal = gprVals.length ? Math.min(...gprVals) : null
  const maxVal = gprVals.length ? Math.max(...gprVals) : null
  const changePct =
    rows.length >= 8 && first?.gpr_index && latest?.gpr_index
      ? (((Number(latest.gpr_index) - Number(first.gpr_index)) / Number(first.gpr_index)) * 100).toFixed(1)
      : null

  useEffect(() => {
    if (!onRangeNote) return
    if (!period || !fullRows.length) {
      onRangeNote(null)
      return
    }
    if (rows.length < fullRows.length && rows.length > 0) {
      onRangeNote(`Index from ${fullRows[0].date.slice(0, 10)} — showing all ${rows.length} days in range`)
    } else if (!rows.length && fullRows.length) {
      onRangeNote(`No GPR data in selected window — index started ${fullRows[0].date.slice(0, 10)}`)
    } else {
      onRangeNote(null)
    }
  }, [period, rows.length, fullRows, onRangeNote])

  useEffect(() => {
    if (!fill) return
    const el = wrapRef.current
    if (!el) return

    const update = () => {
      const next = el.clientHeight
      if (next > 0) setFillHeight(Math.max(FILL_MIN_HEIGHT, next))
    }

    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [fill])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !history.length) return

    const render = () => drawGprChart(canvas, filtered, hoverIndex, chartHeight, indexDays)
    render()
    const observer = new ResizeObserver(render)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [filtered, history.length, hoverIndex, chartHeight, indexDays])

  const onMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !rows.length) return
    const rect = canvas.getBoundingClientRect()
    const x = event.clientX - rect.left
    const gprValsLocal = rows.map((d) => Number(d.gpr_index))
    const points = plotSeries(gprValsLocal, rect.width, rect.height, DEFAULT_PADDING, 0, 1)
    setHoverIndex(nearestIndex(x, points))
  }

  const hoverRow = hoverIndex != null ? rows[hoverIndex] : latest

  const isCorridor = variant === 'corridor'

  return (
    <div className={fill ? `flex flex-col flex-1 min-h-0 h-full ${className}` : className}>
      {!isCorridor && rows.length > 0 && (
        <div className="flex flex-wrap gap-4 mb-3 text-xs">
          <div>
            <span className="text-gray-500 uppercase tracking-wide">Latest</span>
            <div className="text-white font-semibold text-lg">{Number(latest?.gpr_index).toFixed(1)}</div>
          </div>
          {latest?.gpr_7ma != null && (
            <div>
              <span className="text-gray-500 uppercase tracking-wide">7d MA</span>
              <div className="text-[#7aa2ff] font-medium">{Number(latest.gpr_7ma).toFixed(1)}</div>
            </div>
          )}
          {latest?.gpr_30ma != null && (
            <div>
              <span className="text-gray-500 uppercase tracking-wide">30d MA</span>
              <div className="text-gray-300 font-medium">{Number(latest.gpr_30ma).toFixed(1)}</div>
            </div>
          )}
          {minVal != null && maxVal != null && (
            <div>
              <span className="text-gray-500 uppercase tracking-wide">Range</span>
              <div className="text-gray-300 font-medium">{minVal.toFixed(0)} – {maxVal.toFixed(0)}</div>
            </div>
          )}
          {changePct != null && (
            <div>
              <span className="text-gray-500 uppercase tracking-wide">Window Δ</span>
              <div className={Number(changePct) >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                {Number(changePct) >= 0 ? '+' : ''}{changePct}%
              </div>
            </div>
          )}
        </div>
      )}

      <div
        ref={wrapRef}
        className={`relative w-full overflow-hidden ${
          fill ? 'flex-1 min-h-[200px]' : ''
        } ${isCorridor ? 'macro-chart-shell' : 'bg-[#0A101C]/50 rounded-lg border border-white/5'}`}
        style={fill ? undefined : { height: chartHeight }}
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {!rows.length && (
          <div className="flex items-center justify-center h-full text-sm text-gray-500">
            No GPR history yet
          </div>
        )}
        {rows.length > 0 && (
          <>
            <canvas ref={canvasRef} className="w-full h-full" />
            {hoverRow && hoverIndex != null && (
              <div
                className="pointer-events-none absolute top-3 right-3 rounded-md border border-white/10 bg-[#111827]/95 px-3 py-2 text-xs shadow-lg"
              >
                <div className="text-gray-400">{formatDateLong(hoverRow.date)}</div>
                <div className="text-white font-semibold mt-0.5">GPR {Number(hoverRow.gpr_index).toFixed(1)}</div>
                {hoverRow.gpr_7ma != null && (
                  <div className="text-[#7aa2ff]">7MA {Number(hoverRow.gpr_7ma).toFixed(1)}</div>
                )}
                {hoverRow.gpr_30ma != null && (
                  <div className="text-gray-300">30MA {Number(hoverRow.gpr_30ma).toFixed(1)}</div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {rows.length > 0 && !compact && (
        <div className="mt-2 flex flex-wrap gap-4 text-[11px] text-corridor-muted">
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 bg-corridor-alert inline-block" /> GPR</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 bg-primary inline-block" /> 7-day MA</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 bg-corridor-muted inline-block" /> 30-day MA</span>
        </div>
      )}
    </div>
  )
}
