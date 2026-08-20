/** Shared corridor / macro chart palette */
export const CHART_PALETTE = {
  primary: '#adc6ff',
  gpr: '#ff3333',
  gprFill: 'rgba(255, 51, 51, 0.28)',
  gprFillBottom: 'rgba(255, 51, 51, 0.02)',
  niftyUp: '#00c853',
  niftyDown: '#ff3333',
  niftyUpFill: 'rgba(0, 200, 83, 0.22)',
  niftyDownFill: 'rgba(255, 51, 51, 0.22)',
  muted: '#737373',
  axis: '#737373',
  grid: 'rgba(115, 115, 115, 0.12)',
  ma7: '#adc6ff',
  ma30: '#737373',
  baseline: 'rgba(115, 115, 115, 0.35)',
  crosshair: 'rgba(173, 198, 255, 0.35)',
  tooltipBg: '#111111',
  white: '#ffffff',
} as const

export type ChartPadding = { top: number; right: number; bottom: number; left: number }

export const DEFAULT_PADDING: ChartPadding = {
  top: 28,
  right: 16,
  bottom: 36,
  left: 52,
}

/** Extra right margin for dual-axis macro charts */
export const DUAL_AXIS_PADDING: ChartPadding = {
  top: 28,
  right: 48,
  bottom: 36,
  left: 48,
}

export type PlottedPoint = {
  x: number
  y: number
  index: number
}

export function setupCanvas(
  canvas: HTMLCanvasElement,
  height: number,
): { ctx: CanvasRenderingContext2D; width: number; height: number; dpr: number } | null {
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  const dpr = window.devicePixelRatio || 1
  const width = canvas.clientWidth
  canvas.width = width * dpr
  canvas.height = height * dpr
  canvas.style.height = `${height}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  return { ctx, width, height, dpr }
}

export function plotSeries(
  values: number[],
  width: number,
  height: number,
  pad: ChartPadding,
  yMin: number,
  yMax: number,
): PlottedPoint[] {
  const innerW = width - pad.left - pad.right
  const innerH = height - pad.top - pad.bottom
  const yRange = yMax - yMin || 1

  return values.map((value, index) => ({
    index,
    x: pad.left + (index / Math.max(values.length - 1, 1)) * innerW,
    y: pad.top + innerH - ((value - yMin) / yRange) * innerH,
  }))
}

export function yAxisTicks(min: number, max: number, count = 4): number[] {
  const range = max - min || 1
  const step = niceStep(range / Math.max(count - 1, 1))
  const lo = Math.floor(min / step) * step
  const hi = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let v = lo; v <= hi + step * 0.01; v += step) {
    ticks.push(Number(v.toFixed(6)))
  }
  return ticks.slice(0, 8)
}

function niceStep(raw: number): number {
  if (raw <= 0) return 1
  const pow = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / pow
  if (norm <= 1) return pow
  if (norm <= 2) return 2 * pow
  if (norm <= 5) return 5 * pow
  return 10 * pow
}

export function drawGrid(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  pad: ChartPadding,
  yTicks: number[],
  yMin: number,
  yMax: number,
) {
  const innerH = height - pad.top - pad.bottom
  const yRange = yMax - yMin || 1

  ctx.save()
  ctx.strokeStyle = CHART_PALETTE.grid
  ctx.lineWidth = 1
  ctx.fillStyle = CHART_PALETTE.axis
  ctx.font = '11px "JetBrains Mono", ui-monospace, monospace'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'

  yTicks.forEach((tick) => {
    const y = pad.top + innerH - ((tick - yMin) / yRange) * innerH
    ctx.beginPath()
    ctx.moveTo(pad.left, y)
    ctx.lineTo(width - pad.right, y)
    ctx.stroke()
    ctx.fillText(formatAxisNumber(tick), pad.left - 8, y)
  })

  ctx.restore()
}

export function paddedRange(values: number[], padRatio = 0.08): [number, number] {
  if (!values.length) return [0, 1]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = (max - min) * padRatio || 1
  return [min - pad, max + pad]
}

export function drawDualAxisGrid(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  pad: ChartPadding,
  leftTicks: number[],
  leftMin: number,
  leftMax: number,
  rightTicks: number[],
  rightMin: number,
  rightMax: number,
) {
  const innerH = height - pad.top - pad.bottom
  const leftRange = leftMax - leftMin || 1
  const rightRange = rightMax - rightMin || 1

  ctx.save()
  ctx.strokeStyle = CHART_PALETTE.grid
  ctx.lineWidth = 1
  ctx.font = '10px "JetBrains Mono", ui-monospace, monospace'
  ctx.textBaseline = 'middle'

  leftTicks.forEach((tick) => {
    const y = pad.top + innerH - ((tick - leftMin) / leftRange) * innerH
    ctx.beginPath()
    ctx.moveTo(pad.left, y)
    ctx.lineTo(width - pad.right, y)
    ctx.stroke()

    ctx.fillStyle = CHART_PALETTE.niftyUp
    ctx.textAlign = 'right'
    ctx.fillText(formatAxisNumber(tick), pad.left - 6, y)
  })

  rightTicks.forEach((tick) => {
    const y = pad.top + innerH - ((tick - rightMin) / rightRange) * innerH
    ctx.fillStyle = CHART_PALETTE.gpr
    ctx.textAlign = 'left'
    ctx.fillText(formatAxisNumber(tick), width - pad.right + 6, y)
  })

  ctx.restore()
}

export function drawXLabels(
  ctx: CanvasRenderingContext2D,
  labels: string[],
  points: PlottedPoint[],
  height: number,
  pad: ChartPadding,
  maxLabels = 6,
) {
  if (!labels.length || !points.length) return

  ctx.save()
  ctx.fillStyle = CHART_PALETTE.axis
  ctx.font = '10px "JetBrains Mono", ui-monospace, monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'

  const step = Math.max(1, Math.floor((labels.length - 1) / Math.max(maxLabels - 1, 1)))
  for (let i = 0; i < labels.length; i += step) {
    const pt = points[i]
    if (!pt) continue
    ctx.fillText(labels[i], pt.x, height - pad.bottom + 8)
  }
  const last = labels.length - 1
  if (last % step !== 0) {
    const pt = points[last]
    if (pt) ctx.fillText(labels[last], pt.x, height - pad.bottom + 8)
  }

  ctx.restore()
}

export function drawArea(
  ctx: CanvasRenderingContext2D,
  points: PlottedPoint[],
  baselineY: number,
  stroke: string,
  fillTop: string,
  fillBottom: string,
  lineWidth = 2,
) {
  if (points.length < 2) return

  ctx.save()
  const gradient = ctx.createLinearGradient(0, points[0].y, 0, baselineY)
  gradient.addColorStop(0, fillTop)
  gradient.addColorStop(1, fillBottom)

  ctx.beginPath()
  ctx.moveTo(points[0].x, baselineY)
  points.forEach((pt) => ctx.lineTo(pt.x, pt.y))
  ctx.lineTo(points[points.length - 1].x, baselineY)
  ctx.closePath()
  ctx.fillStyle = gradient
  ctx.fill()

  ctx.beginPath()
  points.forEach((pt, i) => {
    if (i === 0) ctx.moveTo(pt.x, pt.y)
    else ctx.lineTo(pt.x, pt.y)
  })
  ctx.strokeStyle = stroke
  ctx.lineWidth = lineWidth
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.stroke()
  ctx.restore()
}

export function drawSeriesWithGaps(
  ctx: CanvasRenderingContext2D,
  values: number[],
  width: number,
  height: number,
  pad: ChartPadding,
  yMin: number,
  yMax: number,
  stroke: string,
  lineWidth = 1.5,
  dashed = false,
) {
  const innerW = width - pad.left - pad.right
  const innerH = height - pad.top - pad.bottom
  const yRange = yMax - yMin || 1
  let segment: PlottedPoint[] = []

  const flush = () => {
    if (segment.length > 1) drawLine(ctx, segment, stroke, lineWidth, dashed)
    segment = []
  }

  values.forEach((value, index) => {
    if (!Number.isFinite(value)) {
      flush()
      return
    }
    segment.push({
      index,
      x: pad.left + (index / Math.max(values.length - 1, 1)) * innerW,
      y: pad.top + innerH - ((value - yMin) / yRange) * innerH,
    })
  })
  flush()
}

export function drawLine(
  ctx: CanvasRenderingContext2D,
  points: PlottedPoint[],
  stroke: string,
  lineWidth = 1.5,
  dashed = false,
) {
  if (points.length < 2) return

  ctx.save()
  ctx.beginPath()
  points.forEach((pt, i) => {
    if (i === 0) ctx.moveTo(pt.x, pt.y)
    else ctx.lineTo(pt.x, pt.y)
  })
  ctx.strokeStyle = stroke
  ctx.lineWidth = lineWidth
  if (dashed) ctx.setLineDash([4, 4])
  ctx.stroke()
  ctx.restore()
}

export function drawHLine(
  ctx: CanvasRenderingContext2D,
  y: number,
  width: number,
  pad: ChartPadding,
  stroke: string,
  dashed = true,
) {
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(pad.left, y)
  ctx.lineTo(width - pad.right, y)
  ctx.strokeStyle = stroke
  ctx.lineWidth = 1
  if (dashed) ctx.setLineDash([5, 5])
  ctx.stroke()
  ctx.restore()
}

export function drawCrosshair(
  ctx: CanvasRenderingContext2D,
  x: number,
  height: number,
  pad: ChartPadding,
  color = 'rgba(173, 198, 255, 0.35)',
) {
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(x, pad.top)
  ctx.lineTo(x, height - pad.bottom)
  ctx.strokeStyle = color
  ctx.lineWidth = 1
  ctx.stroke()
  ctx.restore()
}

export function drawMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  height: number,
  pad: ChartPadding,
  label: string,
  color = '#fbbf24',
) {
  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = 1
  ctx.setLineDash([3, 3])
  ctx.beginPath()
  ctx.moveTo(x, pad.top)
  ctx.lineTo(x, height - pad.bottom)
  ctx.stroke()

  ctx.setLineDash([])
  ctx.fillStyle = color
  ctx.font = '10px Inter, sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText(label, Math.min(x + 4, x), pad.top + 4)
  ctx.restore()
}

export function nearestIndex(mouseX: number, points: PlottedPoint[]): number {
  if (!points.length) return 0
  let best = 0
  let bestDist = Infinity
  points.forEach((pt, i) => {
    const dist = Math.abs(pt.x - mouseX)
    if (dist < bestDist) {
      bestDist = dist
      best = i
    }
  })
  return best
}

export function formatAxisNumber(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}k`
  if (Number.isInteger(value)) return String(value)
  return value.toFixed(1)
}

export function formatDateShort(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
}

export function formatDateLong(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

export function pctChange(first: number, last: number): number {
  if (!first) return 0
  return ((last - first) / first) * 100
}
