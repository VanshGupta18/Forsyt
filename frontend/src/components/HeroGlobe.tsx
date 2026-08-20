import { useEffect, useRef } from 'react'
import { geoOrthographic, geoPath, geoGraticule10, geoInterpolate, geoDistance, type GeoProjection } from 'd3-geo'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'
import landTopology from 'world-atlas/land-110m.json'
import { corridorOperationalRisk, type CorridorRow, type CorridorsPayload } from '../lib/api'
import { corridorCentroidLonLat, corridorRiskColor } from '../lib/corridorGeo'

const SIZE = 640
const GRATICULE = geoGraticule10()
const LAND = feature(landTopology as unknown as Topology, (landTopology as unknown as Topology).objects.land as never)

// [lon, lat] — d3-geo's coordinate convention (not [lat, lon])
const INDIA: [number, number] = [78.9629, 20.5937]
const MAX_GLOBE_NODES = 13
const GLOBE_SCALE = SIZE / 2.05
const INDIA_PHI = (-INDIA[0] * Math.PI) / 180
const INDIA_THETA = -INDIA[1]

type GlobeNode = { location: [number, number]; risk: number; isHub: boolean }

function isFrontFacing(point: [number, number], rotation: [number, number, number]): boolean {
  const center: [number, number] = [-rotation[0], -rotation[1]]
  return geoDistance(point, center) < Math.PI / 2
}

function buildArcPath(
  from: [number, number],
  to: [number, number],
  rotation: [number, number, number],
  projection: GeoProjection,
): string {
  const interpolate = geoInterpolate(from, to)
  let d = ''
  let penDown = false
  for (let i = 0; i <= 32; i++) {
    const point = interpolate(i / 32)
    const xy = isFrontFacing(point, rotation) ? projection(point) : null
    if (!xy) {
      penDown = false
      continue
    }
    d += `${penDown ? 'L' : 'M'}${xy[0]},${xy[1]} `
    penDown = true
  }
  return d.trim()
}

function riskDotRadius(node: GlobeNode): number {
  return node.isHub ? 4 : 2.5 + (Math.min(node.risk, 100) / 100) * 3
}

function riskDotColors(risk: number, isHub: boolean): { fill: string; stroke: string } {
  if (isHub) return { fill: 'rgba(255,255,255,0.95)', stroke: 'rgba(255,255,255,0.9)' }
  const color = corridorRiskColor(risk)
  return { fill: color, stroke: color }
}

function riskArcStroke(risk: number, isHighest: boolean): string {
  if (isHighest) return corridorRiskColor(50)
  return corridorRiskColor(risk)
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function HeroGlobe({
  className,
  corridors = [],
  metadata,
}: {
  className?: string
  corridors?: CorridorRow[]
  metadata?: CorridorsPayload['metadata']
}) {
  const graticuleRef = useRef<SVGPathElement>(null)
  const landRef = useRef<SVGPathElement>(null)
  const nodeRefs = useRef<(SVGGElement | null)[]>([])
  const dotRefs = useRef<(SVGCircleElement | null)[]>([])
  const ringRefs = useRef<(SVGCircleElement | null)[]>([])
  const lineRefs = useRef<(SVGPathElement | null)[]>([])

  const nodesRef = useRef<GlobeNode[]>([{ location: INDIA, risk: 0, isHub: true }])
  const highestRiskIndexRef = useRef<number>(-1)

  const metadataRef = useRef(metadata)
  metadataRef.current = metadata

  useEffect(() => {
    let destroyed = false
    let frame = 0
    let phi = INDIA_PHI
    const reducedMotion = prefersReducedMotion()

    const projection = geoOrthographic()
      .scale(GLOBE_SCALE)
      .translate([SIZE / 2, SIZE / 2])
      .clipAngle(90)
    const path = geoPath(projection)

    function render() {
      const rotation: [number, number, number] = [(phi * 180) / Math.PI, INDIA_THETA, 0]
      projection.rotate(rotation)

      graticuleRef.current?.setAttribute('d', path(GRATICULE) ?? '')
      landRef.current?.setAttribute('d', path(LAND) ?? '')

      for (let i = 0; i < MAX_GLOBE_NODES; i++) {
        const node = nodesRef.current[i]
        const g = nodeRefs.current[i]
        const dot = dotRefs.current[i]
        const ring = ringRefs.current[i]
        const line = lineRefs.current[i]

        if (!node) {
          if (g) g.style.opacity = '0'
          if (line) line.setAttribute('d', '')
          continue
        }

        const xy = isFrontFacing(node.location, rotation) ? projection(node.location) : null
        if (g) {
          if (!xy) {
            g.style.opacity = '0'
          } else {
            g.style.opacity = '1'
            g.setAttribute('transform', `translate(${xy[0]}, ${xy[1]})`)
          }
        }
        if (dot) dot.setAttribute('r', String(riskDotRadius(node)))
        if (dot && ring) {
          const colors = riskDotColors(node.risk, node.isHub)
          dot.setAttribute('fill', colors.fill)
          ring.setAttribute('stroke', colors.stroke)
        }

        if (line) {
          if (node.isHub) {
            line.setAttribute('d', '')
          } else {
            const isHighest = i === highestRiskIndexRef.current
            line.setAttribute('d', buildArcPath(INDIA, node.location, rotation, projection))
            line.setAttribute('stroke', riskArcStroke(node.risk, isHighest))
            line.setAttribute('stroke-dasharray', isHighest ? 'none' : '2 4')
            line.setAttribute('stroke-width', isHighest ? '1.5' : '1')
          }
        }
      }
    }

    function tick() {
      if (destroyed) return
      if (!reducedMotion) phi += 0.0016
      render()
      if (!reducedMotion) frame = requestAnimationFrame(tick)
    }

    render()
    if (!reducedMotion) frame = requestAnimationFrame(tick)

    function applyCorridorRows(rows: CorridorRow[]) {
      const corridorNodes: GlobeNode[] = rows
        .map((c): GlobeNode | null => {
          const key = c.corridor?.toLowerCase()
          const location = key ? corridorCentroidLonLat(metadataRef.current, key) : undefined
          const risk = corridorOperationalRisk(c)
          if (!location || !Number.isFinite(risk)) return null
          return { location, risk, isHub: false }
        })
        .filter((n): n is GlobeNode => n !== null)

      let highest = -1
      let highestRisk = -Infinity
      corridorNodes.forEach((n, i) => {
        if (n.risk > highestRisk) {
          highestRisk = n.risk
          highest = i + 1
        }
      })
      highestRiskIndexRef.current = highest
      nodesRef.current = [{ location: INDIA, risk: 0, isHub: true }, ...corridorNodes]
      render()
    }

    applyCorridorRows(corridors)

    return () => {
      destroyed = true
      cancelAnimationFrame(frame)
    }
  }, [corridors, metadata])

  return (
    <div
      className={`${className ?? 'w-full aspect-square max-w-[520px]'} relative flex items-center justify-center`}
      aria-label="Live corridor risk map centered on India"
    >
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="relative w-full h-full" role="img">
        <circle cx={SIZE / 2} cy={SIZE / 2} r={GLOBE_SCALE} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={1} />
        <path ref={graticuleRef} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={0.6} />
        <path ref={landRef} fill="none" stroke="rgba(255,255,255,0.75)" strokeWidth={1} />
        {Array.from({ length: MAX_GLOBE_NODES }).map((_, i) => (
          <path
            key={`line-${i}`}
            ref={(el) => {
              lineRefs.current[i] = el
            }}
            fill="none"
          />
        ))}
        {Array.from({ length: MAX_GLOBE_NODES }).map((_, i) => (
          <g
            key={`node-${i}`}
            style={{ opacity: 0 }}
            ref={(el) => {
              nodeRefs.current[i] = el
            }}
          >
            <circle
              ref={(el) => {
                ringRefs.current[i] = el
              }}
              r={7}
              fill="#05070d"
              stroke="rgba(255,255,255,0.9)"
              strokeWidth={1}
            />
            <circle
              ref={(el) => {
                dotRefs.current[i] = el
              }}
              r={3}
              fill="rgba(255,255,255,0.9)"
            />
          </g>
        ))}
      </svg>
    </div>
  )
}
