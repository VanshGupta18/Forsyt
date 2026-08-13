export const CORRIDOR_CATEGORIES: Record<string, 'sea' | 'land' | 'strategic'> = {
  strait_of_hormuz: 'sea',
  red_sea_suez: 'sea',
  strait_of_malacca: 'sea',
  cape_of_good_hope: 'sea',
  danish_straits_baltic: 'sea',
  taiwan_south_china_sea: 'sea',
  india_china_lac: 'land',
  india_pakistan_attari: 'land',
  india_bangladesh_petrapole: 'land',
  india_nepal_raxaul: 'land',
  imec: 'strategic',
  instc_chabahar: 'strategic',
}

export const INDIA: [number, number] = [20.5937, 78.9629]

/** Multi-waypoint paths [lat, lon] — aligned with gpr_index/scripts/corridors.py CORRIDOR_PLACES. */
export const CORRIDOR_PATHS: Record<string, { waypoints: [number, number][] }> = {
  strait_of_hormuz: {
    waypoints: [
      [26.0, 52.0],
      [26.5667, 56.25],
      [25.5, 58.5],
    ],
  },
  red_sea_suez: {
    waypoints: [
      [12.5833, 43.3333],
      [20.0, 38.0],
      [30.455, 32.35],
    ],
  },
  strait_of_malacca: {
    waypoints: [
      [5.5, 98.5],
      [2.5, 101.0],
      [1.3, 103.9],
    ],
  },
  cape_of_good_hope: {
    waypoints: [
      [-20.0, 5.0],
      [-34.3568, 18.474],
      [-15.0, 42.0],
    ],
  },
  danish_straits_baltic: {
    waypoints: [
      [55.75, 12.75],
      [57.0, 19.0],
    ],
  },
  taiwan_south_china_sea: {
    waypoints: [
      [2.5, 101.0],
      [12.0, 114.0],
      [24.0, 119.5],
    ],
  },
  india_china_lac: {
    waypoints: [
      [28.0, 77.0],
      [34.1526, 77.5771],
    ],
  },
  india_pakistan_attari: {
    waypoints: [
      [31.63, 74.87],
      [31.6048, 74.572],
    ],
  },
  india_bangladesh_petrapole: {
    waypoints: [
      [22.5, 88.2],
      [23.05, 88.83],
    ],
  },
  india_nepal_raxaul: {
    waypoints: [
      [26.8, 84.7],
      [26.9833, 84.85],
    ],
  },
  imec: {
    waypoints: [
      INDIA,
      [25.2048, 55.2708],
    ],
  },
  instc_chabahar: {
    waypoints: [
      INDIA,
      [25.2919, 60.643],
    ],
  },
}

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

export function corridorRiskColor(risk: number): string {
  if (risk >= 50) return 'var(--color-error)'
  if (risk >= 20) return 'var(--color-tertiary)'
  return 'var(--color-secondary)'
}

export type CorridorMapCategory = 'all' | 'sea' | 'land' | 'strategic'

export function corridorMatchesCategory(key: string, category: CorridorMapCategory): boolean {
  if (category === 'all') return true
  return CORRIDOR_CATEGORIES[key] === category
}
