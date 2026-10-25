// Route: "/countries" — India-relative country risk. A world map of the 15
// tracked countries (click to inspect), a country brief panel, and the Ask
// Forsyt analyst agent. Country risk here is always framed RELATIVE TO INDIA
// (bilateral GPR), not a generic global instability index.
import { useState } from 'react'
import CountryRiskMap from '../components/CountryRiskMap'
import CountryCard from '../components/CountryCard'
import AskForsyt from '../components/AskForsyt'
import { TRACKED } from '../lib/countryGeo'

export default function CountryRiskDashboard() {
  const [selected, setSelected] = useState<string | null>('CH')

  return (
    <div className="corridor-page pb-10 px-margin-page max-w-container-max mx-auto space-y-4">
      <header className="space-y-2 max-w-2xl pt-8">
        <span className="eyebrow-badge">
          <span className="eyebrow-dot" />
          Country risk · relative to India
        </span>
        <h1 className="corridor-display font-headline-lg text-headline-lg">
          How risky is each country to India?
        </h1>
        <p className="font-body-lg text-body-lg text-corridor-muted">
          Bilateral geopolitical risk between India and 15 high-relevance countries, from
          India-related news. Click a country, or ask the analyst.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        {/* Map + picker */}
        <div className="space-y-3">
          <div className="rounded border border-white/10 bg-[#0d0d0d] p-2">
            <CountryRiskMap selected={selected} onSelect={setSelected} />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {TRACKED.map((c) => (
              <button
                key={c.fips}
                onClick={() => setSelected(c.fips)}
                className={`rounded border px-2 py-1 text-[11px] transition-colors ${
                  selected === c.fips
                    ? 'border-corridor-alert text-white'
                    : 'border-white/15 text-white/70 hover:border-corridor-watch'
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel + agent */}
        <aside className="space-y-4">
          <div className="rounded border border-white/10 bg-[#111111]">
            {selected ? (
              <CountryCard fips={selected} />
            ) : (
              <div className="p-4 text-xs text-corridor-muted">Select a country.</div>
            )}
          </div>
          <div className="rounded border border-white/10 bg-[#111111] p-4">
            <AskForsyt />
          </div>
        </aside>
      </div>
    </div>
  )
}
