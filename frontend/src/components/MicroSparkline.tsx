import { useEffect, useRef } from 'react'
import { fetchMarketHistory } from '../lib/api'
import { CHART_PALETTE, drawLine, plotSeries, setupCanvas } from '../lib/chartCanvas'

type Props = {
  symbol: string
  period?: string
  height?: number
  className?: string
}

export default function MicroSparkline({ symbol, period = '1mo', height = 48, className = '' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    let cancelled = false
    let observer: ResizeObserver | undefined

    fetchMarketHistory(symbol, period)
      .then((data) => {
        if (cancelled) return
        const closes = (data.points ?? []).map((p) => p.close).filter(Number.isFinite)
        if (!closes.length) return

        const render = () => {
          const setup = setupCanvas(canvas, height)
          if (!setup) return
          const { ctx, width } = setup
          const pad = { top: 4, right: 4, bottom: 4, left: 4 }
          ctx.clearRect(0, 0, width, height)

          const yMin = Math.min(...closes) * 0.998
          const yMax = Math.max(...closes) * 1.002
          const points = plotSeries(closes, width, height, pad, yMin, yMax)
          const up = closes[closes.length - 1] >= closes[0]
          const stroke = up ? CHART_PALETTE.niftyUp : CHART_PALETTE.niftyDown
          drawLine(ctx, points, stroke, 1.5)
        }

        render()
        observer = new ResizeObserver(render)
        observer.observe(canvas)
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
      observer?.disconnect()
    }
  }, [symbol, period, height])

  return (
    <canvas
      ref={canvasRef}
      className={`w-full ${className}`}
      style={{ height }}
      aria-hidden
    />
  )
}
