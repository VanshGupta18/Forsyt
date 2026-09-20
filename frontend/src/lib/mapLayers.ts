// Optional overlay layers for the corridor map (option 1: static GeoJSON on
// the existing SVG/d3 map). Each layer is a GeoJSON file in /public/geo,
// fetched lazily the first time it's switched on and cached by react-query.
// Live layers (flights, military, cable health) would come later from the
// WorldMonitor developer API — see docs/worldmonitor-api.md.
import { useQuery } from '@tanstack/react-query'
import type { FeatureCollection } from 'geojson'

export type OverlayLayer = {
  key: string
  label: string
  icon: string // emoji, matches the panel's compact look
  color: string
  url: string
}

export const OVERLAY_LAYERS: OverlayLayer[] = [
  { key: 'cables', label: 'Undersea cables', icon: '🔌', color: '#38bdf8', url: '/geo/submarine-cables.geojson' },
  { key: 'pipelines', label: 'Pipelines', icon: '🛢️', color: '#f59e0b', url: '/geo/energy-pipelines.geojson' },
]

// One query per active layer; staleTime Infinity because these static files
// never change during a session. Disabled until the layer is switched on.
export function useOverlayLayer(layer: OverlayLayer, active: boolean) {
  return useQuery({
    queryKey: ['map-overlay', layer.key],
    queryFn: async (): Promise<FeatureCollection> => {
      const res = await fetch(layer.url)
      if (!res.ok) throw new Error(`Failed to load ${layer.label} (${res.status})`)
      return res.json()
    },
    enabled: active,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
