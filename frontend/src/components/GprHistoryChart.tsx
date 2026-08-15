import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchGprHistory, type GprHistoryPoint } from '../lib/api'
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

type Props = {
  height?: number
  className?: string
  variant?: 'default' | 'corridor'
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

function drawGprChart(
  canvas: HTMLCanvasElement,
  history: GprHistoryPoint[],
  hoverIndex: number | null,
  height: number,
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

  const allVals = [
    ...gprVals,
    ...(hasMa7 ? ma7.filter(Number.isFinite) : []),
    ...(hasMa30 ? ma30.filter(Number.isFinite) : []),
    100,
  ]
  const yMin = Math.min(...allVals) * 0.92
  const yMax = Math.max(...allVals) * 1.08
  const yTicks = yAxisTicks(yMin, yMax, 5)

  drawGrid(ctx, width, height, pad, yTicks, yMin, yMax)

  const labels = rows.map((d) => formatDateShort(d.date))
  const gprPoints = plotSeries(gprVals, width, height, pad, yMin, yMax)
  const baselineY = pad.top + (height - pad.top - pad.bottom)

  if (gprVals.some((v) => v <= 100) && gprVals.some((v) => v >= 100)) {
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

export default function GprHistoryChart({ height = CHART_HEIGHT, className = '', variant = 'default' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [history, setHistory] = useState<GprHistoryPoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const rows = validPoints(history)
  const latest = rows[rows.length - 1]
  const first = rows[0]
  const gprVals = rows.map((d) => Number(d.gpr_index))
  const minVal = gprVals.length ? Math.min(...gprVals) : null
  const maxVal = gprVals.length ? Math.max(...gprVals) : null
  const changePct =
    rows.length >= 8 && first?.gpr_index && latest?.gpr_index
      ? (((Number(latest.gpr_index) - Number(first.gpr_index)) / Number(first.gpr_index)) * 100).toFixed(1)
      : null

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchGprHistory(800)
      .then((payload) => setHistory(payload.history ?? []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || loading || error) return

    const render = () => drawGprChart(canvas, history, hoverIndex, height)
    render()
    const observer = new ResizeObserver(render)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [history, error, loading, hoverIndex, height])

  const onMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const canvas = canvasRef.current
    if (!canvas || !rows.length) return
    const rect = canvas.getBoundingClientRect()
    const x = event.clientX - rect.left
    const gprValsLocal = rows.map((d) => Number(d.gpr_index))
    const points = plotSeries(gprValsLocal, rect.width, height, DEFAULT_PADDING, 0, 1)
    setHoverIndex(nearestIndex(x, points))
  }

  const hoverRow = hoverIndex != null ? rows[hoverIndex] : latest

  const isCorridor = variant === 'corridor'

  return (
    <div className={className}>
      {!isCorridor && !loading && !error && rows.length > 0 && (
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
          isCorridor ? 'macro-chart-shell' : 'bg-[#0A101C]/50 rounded-lg border border-white/5'
        }`}
        style={{ height }}
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {loading && (
          <div className="flex items-center justify-center h-full text-sm text-gray-500">
            Loading GPR history…
          </div>
        )}
        {!loading && error && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-sm text-gray-400 px-4 text-center">
            <span>Failed to load GPR history</span>
            <span className="text-xs text-gray-500">{error}</span>
            <button type="button" onClick={load} className="text-xs px-3 py-1 rounded border border-white/20 hover:bg-white/5">
              Retry
            </button>
          </div>
        )}
        {!loading && !error && (
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

      {!loading && !error && rows.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-4 text-[11px] text-corridor-muted">
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 bg-corridor-alert inline-block" /> GPR</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 bg-primary inline-block" /> 7-day MA</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 bg-corridor-muted inline-block" /> 30-day MA</span>
        </div>
      )}
    </div>
  )
}
