import { useState } from 'react'
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps'
import worldData from '../assets/world-110m.json'

export type MapSeverity = 'critical' | 'moderate' | 'stable'

export type MapMarkerData = {
  id: string
  name: string
  coordinates: [number, number]
  severity: MapSeverity
  detail?: string
}

const severityColor: Record<MapSeverity, string> = {
  critical: '#ef4444',
  moderate: '#f59e0b',
  stable: '#10b981',
}

export default function WorldMap({
  markers,
  height = 500,
  center = [20, 15],
  zoom = 1.3,
  activeSeverities,
}: {
  markers: MapMarkerData[]
  height?: number
  center?: [number, number]
  zoom?: number
  activeSeverities?: Set<MapSeverity>
}) {
  const [position, setPosition] = useState<{ coordinates: [number, number]; zoom: number }>({
    coordinates: center,
    zoom,
  })
  const [hovered, setHovered] = useState<MapMarkerData | null>(null)

  const visibleMarkers = activeSeverities
    ? markers.filter((m) => activeSeverities.has(m.severity))
    : markers

  function zoomBy(factor: number) {
    setPosition((p) => ({ ...p, zoom: Math.max(1, Math.min(8, p.zoom * factor)) }))
  }

  return (
    <div className="relative w-full" style={{ height }}>
      <ComposableMap
        projection="geoEqualEarth"
        projectionConfig={{ scale: 165 }}
        style={{ width: '100%', height: '100%' }}
      >
        <ZoomableGroup
          center={position.coordinates}
          zoom={position.zoom}
          minZoom={1}
          maxZoom={8}
          onMoveEnd={(pos) => setPosition(pos)}
        >
          <Geographies geography={worldData}>
            {({ geographies }: { geographies: any[] }) =>
              geographies.map((geo) => (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill="#1b1f2c"
                  stroke="#313442"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: 'none' },
                    hover: { outline: 'none', fill: '#262a37' },
                    pressed: { outline: 'none' },
                  }}
                />
              ))
            }
          </Geographies>

          {visibleMarkers.map((m) => (
            <Marker
              key={m.id}
              coordinates={m.coordinates}
              onMouseEnter={() => setHovered(m)}
              onMouseLeave={() => setHovered((h) => (h?.id === m.id ? null : h))}
            >
              <circle
                r={9}
                fill={severityColor[m.severity]}
                fillOpacity={0.18}
                className="svg-pulse"
              />
              <circle
                r={3.5}
                fill={severityColor[m.severity]}
                stroke="#0a0e1a"
                strokeWidth={1}
                style={{ cursor: 'pointer' }}
              />
            </Marker>
          ))}
        </ZoomableGroup>
      </ComposableMap>

      <div className="pointer-events-none absolute right-4 top-4 z-10 flex items-center gap-1.5 rounded-full border border-secondary/30 bg-[#0a0e1a]/80 px-2.5 py-1 backdrop-blur-md">
        <span className="h-1.5 w-1.5 rounded-full bg-secondary shadow-[0_0_6px_1px_rgba(78,222,163,0.7)] animate-pulse" />
        <span className="font-label-md text-[10px] tracking-widest text-secondary">LIVE</span>
      </div>

      <div className="pointer-events-none absolute bottom-4 left-4 z-10 rounded-md border border-white/10 bg-[#0a0e1a]/70 px-2.5 py-1.5 font-label-md text-[10px] text-gray-400 backdrop-blur-sm">
        LAT {position.coordinates[1].toFixed(2)} · LON {position.coordinates[0].toFixed(2)} · ZOOM{' '}
        {position.zoom.toFixed(1)}x
      </div>

      {hovered && (
        <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-lg border border-white/10 bg-[#0a0e1a]/90 px-3 py-2 backdrop-blur-md">
          <div className="flex items-center gap-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: severityColor[hovered.severity] }}
            />
            <span className="text-xs font-semibold text-white">{hovered.name}</span>
          </div>
          {hovered.detail && <p className="mt-1 text-[11px] text-gray-400 max-w-[220px]">{hovered.detail}</p>}
        </div>
      )}

      <div className="absolute bottom-4 right-4 z-10 flex flex-col overflow-hidden rounded-lg border border-white/10 bg-[#0a0e1a]/80 backdrop-blur-md">
        <button
          aria-label="Zoom in"
          onClick={() => zoomBy(1.5)}
          className="flex h-8 w-8 items-center justify-center text-gray-300 hover:bg-white/10 hover:text-white transition-colors border-b border-white/10"
        >
          +
        </button>
        <button
          aria-label="Zoom out"
          onClick={() => zoomBy(1 / 1.5)}
          className="flex h-8 w-8 items-center justify-center text-gray-300 hover:bg-white/10 hover:text-white transition-colors"
        >
          −
        </button>
      </div>
    </div>
  )
}
