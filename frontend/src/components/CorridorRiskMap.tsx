import { useEffect, useRef, useState } from 'react'
import { geoEquirectangular, geoInterpolate, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'
import type { FeatureCollection } from 'geojson'
import { select } from 'd3-selection'
import { zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior, type ZoomTransform } from 'd3-zoom'
import countries110m from 'world-atlas/countries-110m.json'
import {
  categoryForCorridor,
  corridorMatchesCategory,
  corridorRiskColor,
  corridorRouteKeys,
  corridorWaypoints,
  INDIA,
  type CorridorMapCategory,
} from '../lib/corridorGeo'
import { corridorOperationalRisk, formatCorridorName, type CorridorRow, type CorridorsPayload } from '../lib/api'
import { businessTierLabel, displayStressScore, tierAccentColor } from '../lib/corridorCopy'

const WIDTH = 1000
const HEIGHT = 460
const SAMPLES_PER_LEG = 28

const topo = countries110m as unknown as Topology
const allCountries = (feature(topo, topo.objects.countries) as FeatureCollection).features
const countries = allCountries.filter((f) => f.properties?.name !== 'Antarctica')
const projection = geoEquirectangular().fitSize([WIDTH, HEIGHT], { type: 'FeatureCollection', features: countries })
const pathGenerator = geoPath(projection)
const countryPaths = countries.map((f, i) => ({ key: `country-${i}`, name: f.properties?.name ?? '', d: pathGenerator(f) ?? '' }))

function project([lat, lon]: [number, number]): [number, number] {
  return projection([lon, lat]) ?? [0, 0]
}

function pathFromWaypoints(waypoints: [number, number][]): { d: string; points: [number, number][] } {
  if (waypoints.length < 2) {
    const p = project(waypoints[0] ?? INDIA)
    return { d: `M${p[0]},${p[1]}`, points: [p] }
  }

  const points: [number, number][] = []
  for (let i = 0; i < waypoints.length - 1; i++) {
    const a = waypoints[i]
    const b = waypoints[i + 1]
    const interp = geoInterpolate([a[1], a[0]], [b[1], b[0]])
    const steps = SAMPLES_PER_LEG
    for (let t = 0; t <= steps; t++) {
      if (i > 0 && t === 0) continue
      const [lon, lat] = interp(t / steps)
      points.push(project([lat, lon]))
    }
  }

  const d = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ')
  return { d, points }
}

const indiaPos = project(INDIA)

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

type RouteEntry = {
  key: string
  risk: number
  hasData: boolean
  d: string
  color: string
  points: [number, number][]
  waypoints: [number, number][]
  category: 'sea' | 'land' | 'strategic'
  midpoint: [number, number]
}

export default function CorridorRiskMap({
  corridors,
  metadata,
  selected,
  category = 'all',
  onSelect,
}: {
  corridors: CorridorRow[]
  metadata?: CorridorsPayload['metadata']
  selected: string | null
  category?: CorridorMapCategory
  onSelect: (key: string) => void
}) {
  const now = useClock()
  const timeLabel = now.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })

  const svgRef = useRef<SVGSVGElement>(null)
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const transformRef = useRef<ZoomTransform>(zoomIdentity)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)

  const applyTransform = (next: ZoomTransform) => {
    transformRef.current = next
    setTransform(next)
  }

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    const svgSelection = select(svg)
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .translateExtent([
        [0, 0],
        [WIDTH, HEIGHT],
      ])
      .filter((event) => {
        if (event.type === 'wheel') event.preventDefault()
        // Ignore right-click / ctrl+click so route selection stays predictable.
        if (event.type === 'mousedown' && (event.button === 2 || event.ctrlKey)) return false
        return true
      })
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        applyTransform(event.transform)
        // d3-zoom writes transform on the SVG root; we render on the inner <g> instead.
        svgSelection.attr('transform', null)
      })

    zoomBehaviorRef.current = behavior
    svgSelection.call(behavior).call(behavior.transform, transformRef.current)

    return () => {
      svgSelection.on('.zoom', null).attr('transform', null)
    }
  }, [])

  const zoomBy = (factor: number) => {
    const svg = svgRef.current
    const behavior = zoomBehaviorRef.current
    if (!svg || !behavior) return
    select(svg).call(behavior.scaleBy, factor, [WIDTH / 2, HEIGHT / 2])
  }

  const resetZoom = () => {
    const svg = svgRef.current
    const behavior = zoomBehaviorRef.current
    if (!svg || !behavior) return
    select(svg).call(behavior.transform, zoomIdentity)
  }

  const routeEntries: RouteEntry[] = corridorRouteKeys(metadata)
    .filter((key) => corridorMatchesCategory(metadata, key, category))
    .map((key) => {
      const row = corridors.find((c) => c.corridor?.toLowerCase() === key)
      const risk = row ? corridorOperationalRisk(row) : 0
      const hasData = Boolean(row)
      const waypoints = corridorWaypoints(metadata, key)
      const { d, points } = pathFromWaypoints(waypoints)
      const midIdx = Math.floor(points.length / 2)
      const midpoint = points[midIdx] ?? points[0]
      return {
        key,
        risk,
        hasData,
        d,
        color: corridorRiskColor(risk),
        points,
        waypoints,
        category: categoryForCorridor(metadata, key, row?.category),
        midpoint,
      }
    })

  const topSignal = routeEntries.filter((r) => r.hasData).sort((a, b) => b.risk - a.risk)[0]

  const selectedEntry = selected ? routeEntries.find((r) => r.key === selected && r.hasData) : undefined
  const overlayEntry = selectedEntry ?? topSignal
  const overlayRow = overlayEntry
    ? corridors.find((c) => c.corridor?.toLowerCase() === overlayEntry.key)
    : undefined
  const overlayTierLabel = overlayEntry ? businessTierLabel(overlayEntry.risk).toUpperCase() : null
  const overlayScore = overlayEntry ? displayStressScore(overlayRow ?? {}) : null
  const overlayAccent = overlayEntry ? tierAccentColor(overlayEntry.risk) : undefined

  return (
    <div className="rounded-none overflow-hidden bg-black">
      {overlayEntry && overlayRow && overlayTierLabel && overlayScore != null && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border-b border-white/5"
          style={{ borderLeft: `3px solid ${overlayAccent}` }}
        >
          <span className="corridor-score text-3xl leading-none shrink-0" style={{ color: overlayAccent }}>
            {overlayScore}
          </span>
          <div className="min-w-0 flex flex-col gap-0.5">
            <span className="corridor-kicker shrink-0" style={{ color: overlayAccent }}>
              {overlayTierLabel}
            </span>
            <span className="text-sm text-white/75 truncate">
              {formatCorridorName(overlayRow.corridor, overlayRow.corridor_name)}
            </span>
          </div>
        </div>
      )}

      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="relative z-0 block w-full h-auto cursor-grab active:cursor-grabbing"
          role="img"
          aria-label="World map with trade corridor risk lines"
        >
          <defs>
            <pattern id="corridor-dotgrid" width="26" height="26" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="rgba(255,255,255,0.06)" />
            </pattern>
            <filter id="corridor-beam-blur" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" />
            </filter>
            {routeEntries.map(({ key, points, color }) => {
              const p1 = points[0]
              const p2 = points[points.length - 1]
              return (
                <linearGradient
                  key={key}
                  id={`corridor-grad-${key}`}
                  gradientUnits="userSpaceOnUse"
                  x1={p1[0]}
                  y1={p1[1]}
                  x2={p2[0]}
                  y2={p2[1]}
                >
                  <stop offset="0%" stopColor={color} stopOpacity={0.12} />
                  <stop offset="100%" stopColor={color} stopOpacity={1} />
                </linearGradient>
              )
            })}
          </defs>

          <g transform={transform.toString()}>
            <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="url(#corridor-dotgrid)" />

            {countryPaths.map((c) => (
              <path key={c.key} d={c.d} className="country-path">
                <title>{c.name}</title>
              </path>
            ))}

            {routeEntries.map(({ key, d, color, points, waypoints, category: routeCategory, hasData, midpoint }) => {
              const isSelected = selected === key
              const isDimmed = selected != null && !isSelected
              const isLand = routeCategory === 'land'
              const groupOpacity = isDimmed ? 0.3 : selected == null ? 0.85 : 1
              const gradientRef = `url(#corridor-grad-${key})`
              const row = corridors.find((c) => c.corridor?.toLowerCase() === key)

              return (
                <g
                  key={key}
                  role="button"
                  tabIndex={0}
                  aria-label={`Select ${key.replace(/_/g, ' ')}`}
                  className="cursor-pointer focus:outline-none"
                  opacity={groupOpacity}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelect(key)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelect(key)
                    }
                  }}
                >
                  <path d={d} fill="none" stroke="transparent" strokeWidth={16} />
                  {hasData ? (
                    <>
                      {!isLand && (
                        <path
                          d={d}
                          fill="none"
                          stroke={gradientRef}
                          strokeWidth={isSelected ? 9 : 5}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          opacity={isSelected ? 0.55 : 0.35}
                          filter={isSelected ? 'url(#corridor-beam-blur)' : undefined}
                        />
                      )}
                      <path
                        d={d}
                        fill="none"
                        stroke={gradientRef}
                        strokeWidth={isLand ? (isSelected ? 2.5 : 1.8) : isSelected ? 3.2 : 2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeDasharray={isLand ? '5 4' : undefined}
                      />
                    </>
                  ) : (
                    <path
                      d={d}
                      fill="none"
                      stroke="rgba(255,255,255,0.18)"
                      strokeWidth={1.8}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeDasharray={isLand ? '4 3' : undefined}
                    />
                  )}

                  {points.length > 0 && (
                    <>
                      <circle
                        cx={points[0][0]}
                        cy={points[0][1]}
                        r={2.4}
                        fill={hasData ? color : 'rgba(255,255,255,0.18)'}
                      />
                      <circle
                        cx={points[points.length - 1][0]}
                        cy={points[points.length - 1][1]}
                        r={2.4}
                        fill={hasData ? color : 'rgba(255,255,255,0.18)'}
                      />
                    </>
                  )}

                  {isSelected &&
                    waypoints.slice(1, -1).map((wp, i) => {
                      const p = project(wp)
                      return (
                        <circle
                          key={`${key}-wp-${i}`}
                          cx={p[0]}
                          cy={p[1]}
                          r={3.8}
                          fill={color}
                          stroke="rgba(255,255,255,0.5)"
                          strokeWidth={0.8}
                        />
                      )
                    })}

                  {isSelected && hasData && row && (
                    <text
                      x={midpoint[0]}
                      y={midpoint[1] - 8}
                      textAnchor="middle"
                      fontSize={9}
                      fontWeight={600}
                      fill="rgba(255,255,255,0.9)"
                      className="pointer-events-none select-none"
                    >
                      {formatCorridorName(row.corridor, row.corridor_name)}
                    </text>
                  )}
                </g>
              )
            })}

            <g transform={`translate(${indiaPos[0]},${indiaPos[1]})`}>
              <circle r={6.5} fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth={1.2} opacity={0.6} />
              <circle r={3} fill="#f2f2f2" />
              <text x={9} y={4} className="font-label-md" fontSize={9.5} fill="rgba(255,255,255,0.85)">
                INDIA
              </text>
            </g>
          </g>
        </svg>

        <div className="absolute bottom-3 right-3 z-20 flex flex-col gap-1">
          <button
            type="button"
            onClick={() => zoomBy(1.4)}
            aria-label="Zoom in"
            className="w-7 h-7 flex items-center justify-center rounded-none bg-[#1a1a1a] text-white/80 hover:text-white hover:bg-[#222222] text-sm leading-none"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => zoomBy(1 / 1.4)}
            aria-label="Zoom out"
            className="w-7 h-7 flex items-center justify-center rounded-none bg-[#1a1a1a] text-white/80 hover:text-white hover:bg-[#222222] text-sm leading-none"
          >
            −
          </button>
          <button
            type="button"
            onClick={resetZoom}
            aria-label="Reset zoom"
            className="w-7 h-7 flex items-center justify-center rounded-none bg-[#1a1a1a] text-white/80 hover:text-white hover:bg-[#222222] text-[10px] leading-none"
          >
            ⤾
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-5 items-center px-4 py-3 text-[10px] font-bold uppercase tracking-wider text-corridor-muted">
        <span className="flex items-center gap-2">
          <span className="w-5 h-0.5 bg-corridor-clear" /> Normal
        </span>
        <span className="flex items-center gap-2">
          <span className="w-5 h-0.5 bg-corridor-watch" /> Watch
        </span>
        <span className="flex items-center gap-2">
          <span className="w-5 h-0.5 bg-corridor-alert" /> High alert
        </span>
        <span className="ml-auto corridor-score text-lg text-corridor-muted/60">{timeLabel}</span>
      </div>
    </div>
  )
}
