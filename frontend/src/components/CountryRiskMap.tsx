// CountryRiskMap — flat world map where the 15 India-relative tracked
// countries are clickable. Reuses the same world-atlas + geoEquirectangular
// approach as CorridorRiskMap (no pan/zoom here — this is a country picker).
import { geoEquirectangular, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'
import type { FeatureCollection } from 'geojson'
import countries110m from 'world-atlas/countries-110m.json'
import { FIPS_BY_ATLAS_NAME } from '../lib/countryGeo'

const WIDTH = 1000
const HEIGHT = 460

const topo = countries110m as unknown as Topology
const allFeatures = (feature(topo, topo.objects.countries) as FeatureCollection).features
const features = allFeatures.filter((f) => f.properties?.name !== 'Antarctica')
const projection = geoEquirectangular().fitSize([WIDTH, HEIGHT], {
  type: 'FeatureCollection',
  features,
})
const pathGenerator = geoPath(projection)
const countryPaths = features.map((f, i) => ({
  key: `c-${i}`,
  name: String(f.properties?.name ?? ''),
  fips: FIPS_BY_ATLAS_NAME[String(f.properties?.name ?? '')] ?? null,
  d: pathGenerator(f) ?? '',
}))

export default function CountryRiskMap({
  selected,
  onSelect,
}: {
  selected: string | null
  onSelect: (fips: string) => void
}) {
  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full h-auto select-none"
      role="img"
      aria-label="World map — click a tracked country for its India-relative risk"
    >
      <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="transparent" />
      {countryPaths.map((c) => {
        const tracked = c.fips != null
        const isSelected = tracked && c.fips === selected
        return (
          <path
            key={c.key}
            d={c.d}
            onClick={tracked ? () => onSelect(c.fips as string) : undefined}
            className={
              tracked
                ? `cursor-pointer transition-colors ${
                    isSelected ? 'fill-corridor-alert' : 'fill-white/25 hover:fill-corridor-watch'
                  }`
                : 'fill-white/[0.06]'
            }
            stroke="rgba(255,255,255,0.15)"
            strokeWidth={0.4}
          >
            {tracked && <title>{c.name} — click for India-relative risk</title>}
          </path>
        )
      })}
    </svg>
  )
}
