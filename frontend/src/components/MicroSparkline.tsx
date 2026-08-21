// Tiny inline sparkline (just a colored polyline, no axes/labels) drawn
// directly as an SVG — used inside PulseCard, so no <canvas> setup is needed
// for something this small.
type Props = {
  points: Array<{ date: string; close: number }>
  height?: number
  className?: string
}

export default function MicroSparkline({ points, height = 48, className = '' }: Props) {
  const closes = points.map((p) => p.close).filter(Number.isFinite)
  if (closes.length < 2) {
    return <div className={className} style={{ height }} aria-hidden />
  }

  const width = 120
  const pad = 2
  const min = Math.min(...closes) * 0.998
  const max = Math.max(...closes) * 1.002
  const range = max - min || 1
  const up = closes[closes.length - 1] >= closes[0]
  const stroke = up ? '#00c853' : '#ff3333'

  const plotted = closes.map((value, index) => {
    const x = pad + (index / Math.max(closes.length - 1, 1)) * (width - pad * 2)
    const y = pad + (height - pad * 2) - ((value - min) / range) * (height - pad * 2)
    return `${x},${y}`
  })

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      style={{ height, width: '100%' }}
      preserveAspectRatio="none"
      aria-hidden
    >
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={plotted.join(' ')}
      />
    </svg>
  )
}
