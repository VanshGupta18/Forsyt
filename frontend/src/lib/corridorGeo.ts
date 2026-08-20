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
