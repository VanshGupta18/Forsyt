// Bridges the world-atlas map (keyed by country NAME) to the Forsyt API
// (keyed by FIPS code). Only the 15 tracked countries are listed; every other
// country on the map is inert.
//
// `atlasName` must match `feature.properties.name` from
// world-atlas/countries-110m.json exactly. (Singapore is omitted from the
// 110m polygons — it stays reachable via the country picker, just not the map.)

export const TRACKED: Array<{ fips: string; name: string; atlasName: string }> = [
  { fips: 'CH', name: 'China',         atlasName: 'China' },
  { fips: 'PK', name: 'Pakistan',      atlasName: 'Pakistan' },
  { fips: 'US', name: 'United States', atlasName: 'United States of America' },
  { fips: 'RS', name: 'Russia',        atlasName: 'Russia' },
  { fips: 'IR', name: 'Iran',          atlasName: 'Iran' },
  { fips: 'SA', name: 'Saudi Arabia',  atlasName: 'Saudi Arabia' },
  { fips: 'AE', name: 'UAE',           atlasName: 'United Arab Emirates' },
  { fips: 'BG', name: 'Bangladesh',    atlasName: 'Bangladesh' },
  { fips: 'CE', name: 'Sri Lanka',     atlasName: 'Sri Lanka' },
  { fips: 'NP', name: 'Nepal',         atlasName: 'Nepal' },
  { fips: 'BM', name: 'Myanmar',       atlasName: 'Myanmar' },
  { fips: 'AF', name: 'Afghanistan',   atlasName: 'Afghanistan' },
  { fips: 'IS', name: 'Israel',        atlasName: 'Israel' },
  { fips: 'QA', name: 'Qatar',         atlasName: 'Qatar' },
  { fips: 'SN', name: 'Singapore',     atlasName: 'Singapore' },
]

export const FIPS_BY_ATLAS_NAME: Record<string, string> = Object.fromEntries(
  TRACKED.map((c) => [c.atlasName, c.fips]),
)

export function channelLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
