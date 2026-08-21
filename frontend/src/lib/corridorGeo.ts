// ---------------------------------------------------------------------------
// Geography helpers shared by the two map components (HeroGlobe.tsx and
// CorridorRiskMap.tsx) and by corridor lookups elsewhere. A quick note on
// coordinate order, since it trips people up: this file's own `INDIA`
// constant and the backend's `metadata[...].centroid` use the everyday
// [latitude, longitude] order, but the d3-geo library (used by the two map
// components) expects [longitude, latitude] instead. Functions here that
// hand coordinates to d3-geo — like corridorCentroidLonLat — do the swap
// explicitly so callers don't have to remember which order is which.
// ---------------------------------------------------------------------------
import type { CorridorCategory, CorridorsPayload } from './api'

export const INDIA: [number, number] = [20.5937, 78.9629]

export type CorridorMapCategory = 'all' | 'sea' | 'land' | 'strategic'

export type CorridorMetadataEntry = NonNullable<CorridorsPayload['metadata']>[string]

// Short keywords for /api/events/feed corridor ILIKE filter.
export const CORRIDOR_SEARCH_TERMS: Record<string, string> = {
  strait_of_hormuz: 'Hormuz',
  red_sea_suez: 'Red Sea',
  strait_of_malacca: 'Malacca',
  cape_of_good_hope: 'Cape of Good Hope',
  danish_straits_baltic: 'Baltic',
  taiwan_south_china_sea: 'South China Sea',
  india_china_lac: 'Ladakh',
  india_pakistan_attari: 'Wagah',
  india_bangladesh_petrapole: 'Petrapole',
  india_nepal_raxaul: 'Raxaul',
  imec: 'IMEC',
  instc_chabahar: 'Chabahar',
}

export function corridorRouteKeys(metadata?: CorridorsPayload['metadata']): string[] {
  return Object.keys(metadata ?? {})
}

// Returns the list of [lat, lon] points that make up one corridor's route
// line on the map. Prefers the backend's explicit `waypoints` (a hand-picked
// path, e.g. hugging a coastline) and falls back to just the corridor's
// single `centroid` point (a straight line with no intermediate stops) if no
// waypoints were provided.
export function corridorWaypoints(
  metadata: CorridorsPayload['metadata'] | undefined,
  corridorId: string,
): [number, number][] {
  const entry = metadata?.[corridorId.toLowerCase()]
  const waypoints = entry?.waypoints
  if (waypoints?.length) {
    return waypoints.map((wp) => [wp[0], wp[1]] as [number, number])
  }
  const centroid = entry?.centroid
  if (centroid) return [[centroid.lat, centroid.lon]]
  return []
}

// Same idea as corridorWaypoints, but returns just the single centroid point
// — and in [lon, lat] order (swapped from the backend's [lat, lon]) because
// this is specifically for handing straight to d3-geo, which HeroGlobe.tsx
// uses to place a risk dot on the globe.
export function corridorCentroidLonLat(
  metadata: CorridorsPayload['metadata'] | undefined,
  corridorId: string,
): [number, number] | undefined {
  const centroid = metadata?.[corridorId.toLowerCase()]?.centroid
  if (!centroid) return undefined
  return [centroid.lon, centroid.lat]
}

export function categoryForCorridor(
  metadata: CorridorsPayload['metadata'] | undefined,
  corridorId: string,
  rowCategory?: CorridorCategory,
): CorridorCategory {
  return rowCategory ?? metadata?.[corridorId.toLowerCase()]?.category ?? 'sea'
}

// Same 50 / 20 risk thresholds used throughout corridorCopy.ts, but returning
// a CSS custom-property reference instead of a Tailwind class name — used by
// the two map components, which draw with raw SVG/canvas colors rather than
// className strings.
export function corridorRiskColor(risk: number): string {
  if (risk >= 50) return 'var(--color-error)'
  if (risk >= 20) return 'var(--color-tertiary)'
  return 'var(--color-secondary)'
}

export function corridorMatchesCategory(
  metadata: CorridorsPayload['metadata'] | undefined,
  key: string,
  category: CorridorMapCategory,
): boolean {
  if (category === 'all') return true
  return categoryForCorridor(metadata, key) === category
}
