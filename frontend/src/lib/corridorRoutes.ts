// ---------------------------------------------------------------------------
// Powers the "Find a route" box on the Corridor Risk page: the user types an
// origin/destination (free text, e.g. "Mumbai" → "Rotterdam") and this file
// guesses which tracked corridors that shipment would pass through. This is
// intentionally simple — plain keyword matching, no geocoding or real routing
// engine (see the "v1, no ML" comment below) — so treat its suggestions as a
// rough hint, not authoritative routing.
//
// NOTE: only the six sea corridors are tracked. The land-border corridors
// (Attari, Petrapole, Raxaul, Ladakh) were retired because they carry no
// quantified India trade exposure and could never be matched to articles, so
// road/rail lookups intentionally return nothing rather than pointing at a
// route with no score behind it. See INACTIVE_CORRIDORS in
// gpr_index/scripts/corridors.py for the full rationale.
// ---------------------------------------------------------------------------
export type RouteMode = 'sea' | 'road' | 'rail'

const SEA_EUROPE = ['red_sea_suez', 'strait_of_hormuz', 'cape_of_good_hope', 'danish_straits_baltic']
const SEA_EAST = ['strait_of_malacca', 'taiwan_south_china_sea']

function includesAny(text: string, terms: string[]): boolean {
  const lower = text.toLowerCase()
  return terms.some((term) => lower.includes(term))
}

/** Rule-based lane → corridor mapping (v1, no ML). */
// Both origin and destination text are lower-cased and mashed together into
// one `blob` string, then checked for keywords (city/country names). This
// means it can't tell origin from destination, and only recognizes the
// place names hard-coded in `includesAny(...)` calls below — anything else
// falls through to a generic guess across all tracked sea corridors.
export function suggestCorridors(origin: string, destination: string, mode: RouteMode): string[] {
  const from = origin.trim()
  const to = destination.trim()
  if (!from || !to) return []

  // No land corridor is tracked any more, so an overland lane has no
  // scored route to point at. Returning [] lets the caller show the
  // "no tracked route" state instead of naming a corridor with no data.
  if (mode === 'road' || mode === 'rail') return []

  const blob = `${from} ${to}`
  if (includesAny(blob, ['europe', 'rotterdam', 'hamburg', 'uk', 'mediterranean'])) {
    return ['red_sea_suez', 'strait_of_hormuz', 'danish_straits_baltic']
  }
  if (includesAny(blob, ['china', 'shanghai', 'hong kong', 'taiwan', 'singapore', 'malaysia'])) {
    return ['strait_of_malacca', 'taiwan_south_china_sea']
  }
  if (includesAny(blob, ['uae', 'dubai', 'middle east', 'iran', 'chabahar'])) {
    return ['strait_of_hormuz']
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
  cape_of_good_hope: 'Already the long-way-round option — build schedule buffer rather than rerouting.',
  danish_straits_baltic: 'Confirm Baltic port calls and ice-season timing with your forwarder.',
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
