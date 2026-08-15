import { useEffect, useRef } from 'react'
import { geoOrthographic, geoPath, geoGraticule10, geoInterpolate, geoDistance, type GeoProjection } from 'd3-geo'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'
import landTopology from 'world-atlas/land-110m.json'
import { fetchCorridors } from '../lib/api'

const SIZE = 640
const GRATICULE = geoGraticule10()
const LAND = feature(landTopology as unknown as Topology, (landTopology as unknown as Topology).objects.land as never)

// [lon, lat] — d3-geo's coordinate convention (not [lat, lon])
const INDIA: [number, number] = [78.9629, 20.5937]
const CORRIDOR_LOCATIONS: Record<string, [number, number]> = {
  strait_of_hormuz: [56.25, 26.5],
  red_sea_suez: [38.0, 20.0],
  strait_of_malacca: [101.0, 2.5],
  cape_of_good_hope: [18.5, -34.0],
  danish_straits_baltic: [11.0, 56.0],
  taiwan_south_china_sea: [113.0, 12.0],
  india_china_lac: [78.5, 34.0],
  india_pakistan_attari: [74.6, 31.6],
  india_bangladesh_petrapole: [88.4, 23.0],
  india_nepal_raxaul: [84.9, 27.0],
  imec: [55.3, 25.2],
  instc_chabahar: [60.6, 25.3],
}
const MAX_NODES = 1 + Object.keys(CORRIDOR_LOCATIONS).length

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

export default function HeroGlobe({ className }: { className?: string }) {
  const graticuleRef = useRef<SVGPathElement>(null)
  const landRef = useRef<SVGPathElement>(null)
  const nodeRefs = useRef<(SVGGElement | null)[]>([])
  const dotRefs = useRef<(SVGCircleElement | null)[]>([])
  const lineRefs = useRef<(SVGPathElement | null)[]>([])

  const nodesRef = useRef<GlobeNode[]>([{ location: INDIA, risk: 0, isHub: true }])
  const highestRiskIndexRef = useRef<number>(-1)

  useEffect(() => {
    let destroyed = false
    let frame = 0
    let phi = 0
    const thetaDeg = -22

    const projection = geoOrthographic()
      .scale(SIZE / 2.18)
      .translate([SIZE / 2, SIZE / 2])
      .clipAngle(90)
    const path = geoPath(projection)

    function render() {
      const rotation: [number, number, number] = [(phi * 180) / Math.PI, thetaDeg, 0]
      projection.rotate(rotation)

      graticuleRef.current?.setAttribute('d', path(GRATICULE) ?? '')
      landRef.current?.setAttribute('d', path(LAND) ?? '')

      for (let i = 0; i < MAX_NODES; i++) {
        const node = nodesRef.current[i]
        const g = nodeRefs.current[i]
        const dot = dotRefs.current[i]
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

        if (line) {
          if (node.isHub) {
            line.setAttribute('d', '')
          } else {
            const isHighest = i === highestRiskIndexRef.current
            line.setAttribute('d', buildArcPath(INDIA, node.location, rotation, projection))
            line.setAttribute('stroke', isHighest ? 'var(--color-tertiary)' : 'rgba(255,255,255,0.35)')
            line.setAttribute('stroke-dasharray', isHighest ? 'none' : '2 4')
            line.setAttribute('stroke-width', isHighest ? '1.5' : '1')
          }
        }
      }
    }

    function tick() {
      if (destroyed) return
      phi += 0.0016
      render()
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)

    function applyCorridorPayload(payload: Awaited<ReturnType<typeof fetchCorridors>>) {
      const corridorNodes: GlobeNode[] = (payload.corridors ?? [])
        .map((c): GlobeNode | null => {
          const key = c.corridor?.toLowerCase()
          const location = key ? CORRIDOR_LOCATIONS[key] : undefined
          if (!location || c.corridor_risk == null) return null
          return { location, risk: c.corridor_risk, isHub: false }
        })
        .filter((n): n is GlobeNode => n !== null)

      let highest = -1
      let highestRisk = -Infinity
      corridorNodes.forEach((n, i) => {
        if (n.risk > highestRisk) {
          highestRisk = n.risk
          highest = i + 1 // +1: India occupies slot 0
        }
      })
      highestRiskIndexRef.current = highest
      nodesRef.current = [{ location: INDIA, risk: 0, isHub: true }, ...corridorNodes]
    }

    fetchCorridors()
      .then((payload) => {
        if (destroyed) return
        applyCorridorPayload(payload)
      })
      .catch(() => undefined)

    const pollId = window.setInterval(() => {
      fetchCorridors()
        .then((payload) => {
          if (destroyed) return
          applyCorridorPayload(payload)
        })
        .catch(() => undefined)
    }, 15 * 60 * 1000)

    return () => {
      destroyed = true
      cancelAnimationFrame(frame)
      window.clearInterval(pollId)
    }
  }, [])

  return (
    <div className={`${className ?? 'h-[640px] w-[640px]'} relative flex items-center justify-center`}>
      <div
        className="absolute rounded-full border border-white/10"
        style={{ width: '124%', height: '124%', transform: 'rotateX(78deg)' }}
      />
      <div
        className="absolute rounded-full border border-white/[0.07]"
        style={{ width: '148%', height: '148%', transform: 'rotateX(80deg) rotateZ(10deg)' }}
      />
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="relative w-full h-full" aria-hidden>
        <circle cx={SIZE / 2} cy={SIZE / 2} r={SIZE / 2.18} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={1} />
        <path ref={graticuleRef} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={0.6} />
        <path ref={landRef} fill="none" stroke="rgba(255,255,255,0.75)" strokeWidth={1} />
        {Array.from({ length: MAX_NODES }).map((_, i) => (
          <path
            key={`line-${i}`}
            ref={(el) => {
              lineRefs.current[i] = el
            }}
            fill="none"
          />
        ))}
        {Array.from({ length: MAX_NODES }).map((_, i) => (
          <g
            key={`node-${i}`}
            style={{ opacity: 0 }}
            ref={(el) => {
              nodeRefs.current[i] = el
            }}
          >
            <circle r={7} fill="#05070d" stroke="rgba(255,255,255,0.9)" strokeWidth={1} />
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
