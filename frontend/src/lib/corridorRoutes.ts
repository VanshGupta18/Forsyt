// ---------------------------------------------------------------------------
// Powers the "Find a route" box on the Corridor Risk page: the user types an
// origin/destination (free text, e.g. "Mumbai" → "Rotterdam") and this file
// guesses which of the 12 tracked corridors that shipment would pass
// through. This is intentionally simple — plain keyword matching, no
// geocoding or real routing engine (see the "v1, no ML" comment below) — so
// treat its suggestions as a rough hint, not authoritative routing.
// ---------------------------------------------------------------------------
export type RouteMode = 'sea' | 'road' | 'rail'

const SEA_EUROPE = ['red_sea_suez', 'strait_of_hormuz', 'cape_of_good_hope', 'danish_straits_baltic']
const SEA_EAST = ['strait_of_malacca', 'taiwan_south_china_sea']
const LAND = [
  'india_pakistan_attari',
  'india_bangladesh_petrapole',
  'india_nepal_raxaul',
  'india_china_lac',
]

function includesAny(text: string, terms: string[]): boolean {
  const lower = text.toLowerCase()
  return terms.some((term) => lower.includes(term))
}

/** Rule-based lane → corridor mapping (v1, no ML). */
// Both origin and destination text are lower-cased and mashed together into
// one `blob` string, then checked for keywords (city/country names). This
// means it can't tell origin from destination, and only recognizes the
// place names hard-coded in `includesAny(...)` calls below — anything else
// falls through to a generic guess (all land corridors, or all sea
// corridors, depending on `mode`).
export function suggestCorridors(origin: string, destination: string, mode: RouteMode): string[] {
  const from = origin.trim()
  const to = destination.trim()
  if (!from || !to) return []

  const blob = `${from} ${to}`
  if (mode === 'road' || mode === 'rail') {
    if (includesAny(blob, ['nepal', 'birgunj', 'raxaul'])) return ['india_nepal_raxaul']
    if (includesAny(blob, ['bangladesh', 'dhaka', 'petrapole'])) return ['india_bangladesh_petrapole']
    if (includesAny(blob, ['pakistan', 'lahore', 'wagah', 'attari'])) return ['india_pakistan_attari']
    if (includesAny(blob, ['china', 'ladakh', 'lhasa'])) return ['india_china_lac']
    return LAND
  }

  if (includesAny(blob, ['europe', 'rotterdam', 'hamburg', 'uk', 'mediterranean'])) {
    return ['red_sea_suez', 'strait_of_hormuz', 'danish_straits_baltic']
  }
  if (includesAny(blob, ['china', 'shanghai', 'hong kong', 'taiwan', 'singapore', 'malaysia'])) {
    return ['strait_of_malacca', 'taiwan_south_china_sea']
  }
  if (includesAny(blob, ['uae', 'dubai', 'middle east', 'iran', 'chabahar'])) {
    return ['strait_of_hormuz', 'instc_chabahar', 'imec']
  }
  if (includesAny(blob, ['africa', 'cape'])) {
    return ['cape_of_good_hope', 'red_sea_suez']
  }
  return [...SEA_EUROPE, ...SEA_EAST]
}

export const CORRIDOR_ALTERNATIVES: Record<string, string> = {
  strait_of_hormuz: 'Consider Cape of Good Hope routing (+ longer transit, avoids Hormuz chokepoint).',
  red_sea_suez: 'Consider Cape routing or longer Malacca–Europe path if Suez/Red Sea stays elevated.',
  taiwan_south_china_sea: 'Monitor Malacca approach and port congestion; build buffer for East Asia lanes.',
  strait_of_malacca: 'No direct substitute — increase lead time and track South China Sea spillover.',
  india_pakistan_attari: 'Buffer customs clearance; consider alternate land routes if border closures reported.',
  india_bangladesh_petrapole: 'Allow extra border dwell time; confirm Petrapole queue status with freight forwarder.',
  india_china_lac: 'Land-border consignments may face delays — confirm clearance before dispatch.',
}

export const CONTINGENCY_CHECKLIST: Record<string, string[]> = {
  High: [
    'Review marine / cargo insurance cover',
    'Notify customers of possible delay',
    'Add 3–7 day buffer to committed ETAs',
    'Confirm alternative routing with forwarder',
  ],
  Medium: [
    'Monitor headlines daily until score eases',
    'Avoid locking fragile just-in-time slots',
    'Confirm port and border operating status',
  ],
  Low: ['Standard routing — recheck before next booking tranche'],
}
