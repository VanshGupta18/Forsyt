// ---------------------------------------------------------------------------
// HeroGlobe — the slowly-rotating 3D-look globe on the Home page, centered on
// India, with thin arcs reaching out to the riskiest trade corridors.
//
// BACKGROUND FOR NEWCOMERS: `d3-geo` is a small part of the larger D3.js
// library that specializes in "geographic projections" — the math for
// squashing the surface of a sphere (the Earth) onto a flat 2D drawing
// surface (your screen). There is no single correct way to do this — every
// world map ever drawn has picked a projection, and each one makes different
// tradeoffs about what gets distorted. This component uses
// `geoOrthographic()`, which is the projection that makes the Earth look
// like a photo taken from space: a circle, with the far side of the globe
// invisible, and land near the edges visibly curving away — i.e. it looks
// like an actual 3D globe even though it's drawn as flat 2D shapes. (Compare
// with CorridorRiskMap.tsx, which uses `geoEquirectangular()` instead — the
// familiar flat rectangular world map where the whole world is visible at
// once but sizes near the poles are stretched.)
//
// A `GeoProjection` (the `projection` object below) is a function you can
// call as `projection([longitude, latitude])` to get back `[x, y]` pixel
// coordinates for that point on the current view of the globe — and
// `geoPath(projection)` wraps that into a function that converts a whole
// GeoJSON shape (like the outline of a continent) into an SVG `<path>` `d`
// attribute string in one call. IMPORTANT: d3-geo always takes coordinates
// as `[longitude, latitude]` — the opposite order from the everyday
// "latitude, longitude" you'd say out loud or see in `corridorGeo.ts`'s
// `INDIA` constant. Watch for `.reverse()`-style swaps around this file's
// boundary with that other file.
//
// WHERE THE LAND SHAPE COMES FROM: `world-atlas` is an npm package that
// ships pre-built, heavily simplified maps of the world as "TopoJSON" — a
// compact format that's essentially GeoJSON but with shared borders between
// countries stored once instead of duplicated. `topojson-client`'s
// `feature()` function decodes that TopoJSON back into ordinary GeoJSON
// (the format `geoPath` understands) — here it decodes the single combined
// landmass shape (`land-110m.json`, "110m" meaning it's simplified to about
// 1:110,000,000 scale, i.e. deliberately low-detail/small file size, which
// is plenty for a small hero graphic).
//
// WHY REFS INSTEAD OF REACT STATE: This globe redraws every animation frame
// (~60 times/second) to rotate smoothly. Putting the rotation angle in React
// state and calling setState 60 times/second would cause 60 full component
// re-renders/second — wasteful and janky. Instead, this component renders
// its SVG elements ONCE, keeps direct references to them via `useRef`, and
// on every animation frame just mutates their attributes directly
// (`el.setAttribute(...)`) — bypassing React's re-render cycle entirely for
// the animation, the same way you'd animate with plain DOM APIs. React only
// re-runs this component when the `corridors`/`metadata` props change.
// ---------------------------------------------------------------------------
import { useEffect, useRef } from 'react'
import { geoOrthographic, geoPath, geoGraticule10, geoInterpolate, geoDistance, type GeoProjection } from 'd3-geo'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'
import landTopology from 'world-atlas/land-110m.json'
import { corridorOperationalRisk, type CorridorRow, type CorridorsPayload } from '../lib/api'
import { corridorCentroidLonLat, corridorRiskColor } from '../lib/corridorGeo'

const SIZE = 640
// geoGraticule10() generates the faint latitude/longitude grid lines (every
// 10 degrees) drawn on the globe purely for visual texture — it carries no
// real data.
const GRATICULE = geoGraticule10()
// Decode the bundled TopoJSON land data into a GeoJSON shape once, at module
// load time (not inside the component) — it's the same for every instance
// of this component and never changes, so there's no reason to redo this
// decode on every render.
const LAND = feature(landTopology as unknown as Topology, (landTopology as unknown as Topology).objects.land as never)

// [lon, lat] — d3-geo's coordinate convention (not [lat, lon])
const INDIA: [number, number] = [78.9629, 20.5937]
const MAX_GLOBE_NODES = 13
const GLOBE_SCALE = SIZE / 2.05
const INDIA_PHI = (-INDIA[0] * Math.PI) / 180
const INDIA_THETA = -INDIA[1]

type GlobeNode = { location: [number, number]; risk: number; isHub: boolean }

// A globe only ever shows HALF the Earth's surface at once — the near side
// facing the viewer. `geoDistance` computes the great-circle (shortest path
// on a sphere) angular distance, in radians, between two [lon, lat] points.
// The center of the visible hemisphere is the point directly opposite the
// current rotation, and any point less than 90 degrees (`Math.PI / 2`
// radians) away from that center is on the near/visible side. This is used
// both to decide whether to draw a risk dot at all, and to fade an arc in
// and out as it wraps around the back of the globe.
function isFrontFacing(point: [number, number], rotation: [number, number, number]): boolean {
  const center: [number, number] = [-rotation[0], -rotation[1]]
  return geoDistance(point, center) < Math.PI / 2
}

// Builds the SVG path string for one curved arc from India to a corridor's
// location. `geoInterpolate(from, to)` returns a function that, given a
// fraction 0..1, gives back the point that fraction of the way along the
// great-circle route between `from` and `to` — i.e. it traces the *shortest
// path on the globe's surface*, which curves when projected flat, rather
// than a straight line. This walks that path in 32 small steps, projecting
// each step to screen coordinates. Whenever a step falls on the globe's far
// side (`isFrontFacing` is false), the pen is lifted (`penDown = false`) so
// the arc visually disappears instead of being drawn straight through the
// globe — the `M` (move-to, start a new sub-path) vs `L` (line-to, continue
// the current sub-path) SVG path commands are how that's expressed.
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
    // `phi` is the current spin angle (in radians) — it increases a tiny bit
    // every frame in `tick()` below to make the globe rotate. It starts at
    // INDIA_PHI so the globe opens already facing India instead of snapping
    // there after a spin.
    let phi = INDIA_PHI
    const reducedMotion = prefersReducedMotion()

    // Build the projection ONCE for this component instance. `.scale()` sets
    // the globe's pixel radius, `.translate()` centers it in the SIZE x SIZE
    // SVG viewport, and `.clipAngle(90)` is what makes it a globe instead of
    // a full flattened sphere — it tells d3 "don't draw anything more than
    // 90 degrees from the center", i.e. hide the far hemisphere.
    const projection = geoOrthographic()
      .scale(GLOBE_SCALE)
      .translate([SIZE / 2, SIZE / 2])
      .clipAngle(90)
    // geoPath(projection) turns that projection into a helper that converts
    // a whole GeoJSON shape (like LAND, the world's landmasses) into one SVG
    // path `d` string — used just below to draw the outline of the continents.
    const path = geoPath(projection)

    // Draws one frame: re-rotates the projection to the current spin angle,
    // then repaints the graticule, land outline, and every corridor risk
    // dot + connecting arc at their new screen positions for that rotation.
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

    // `requestAnimationFrame` asks the browser to call `tick()` again right
    // before its next screen repaint (typically ~60 times/second) — this is
    // the standard way to drive smooth animations in the browser, rather
    // than using `setInterval` with a guessed delay. Each tick nudges `phi`
    // forward a tiny amount (skipped entirely if the user's OS/browser
    // requests reduced motion) and redraws. `frame` stores the request's ID
    // so the cleanup function below can cancel it if this component unmounts
    // mid-spin.
    function tick() {
      if (destroyed) return
      if (!reducedMotion) phi += 0.0016
      render()
      if (!reducedMotion) frame = requestAnimationFrame(tick)
    }

    render()
    if (!reducedMotion) frame = requestAnimationFrame(tick)

    // Recomputes which corridors get a risk dot + arc whenever the
    // `corridors` prop changes (e.g. a fresh API response comes in) —
    // separate from the spin animation above, which keeps running
    // regardless of when new data arrives.
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
