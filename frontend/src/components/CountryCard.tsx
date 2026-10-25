// CountryCard — India-relative risk brief for one country. Fetches
// /api/pages/country/<fips> and renders score, band, trend, channel bars,
// a 30-day sparkline, corridors, market, and the AI brief. Degrades to an
// honest "low-confidence / insufficient data" state (never blank/crash).
import { useQuery } from '@tanstack/react-query'
import { countryBandColor, fetchCountry } from '../lib/api'
import { channelLabel } from '../lib/countryGeo'
import ScoreBar from './ScoreBar'
import MicroSparkline from './MicroSparkline'

const TREND_ARROW: Record<string, string> = { rising: '↑', falling: '↓', stable: '→' }

export default function CountryCard({ fips }: { fips: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['country', fips],
    queryFn: () => fetchCountry(fips),
  })

  if (isLoading) {
    return <div className="p-4 text-xs text-corridor-muted">Loading country brief…</div>
  }
  if (isError || !data) {
    return <div className="p-4 text-xs text-corridor-alert">Couldn't load this country.</div>
  }

  const { country, score, channels, history, corridors, market, summary, facts, macro, ports, energy, top_events } = data
  const fmtNum = (n?: number | null) =>
    n == null ? '—' : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n.toLocaleString()
  const channelEntries = Object.entries(channels)
    .filter(([k]) => k !== 'none')
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
  const spark = history.map((h) => ({ date: h.date, close: h.value }))

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="font-label-md text-corridor-muted uppercase tracking-wide text-[10px]">
            Country brief · {country.fips}
          </div>
          <h2 className="text-xl font-semibold text-white">
            {facts?.flag && <span className="mr-1.5">{facts.flag}</span>}
            {country.name}
          </h2>
        </div>
        {score.low_confidence && (
          <span className="rounded border border-corridor-watch/40 px-1.5 py-0.5 text-[10px] text-corridor-watch">
            low confidence
          </span>
        )}
      </div>

      {/* Score */}
      <div className="flex items-end gap-3">
        <div className={`text-4xl font-bold tabular-nums ${countryBandColor(score.band)}`}>
          {score.value ?? '—'}
          {score.value != null && <span className="text-lg text-corridor-muted">/india-rel</span>}
        </div>
        {score.band && (
          <div className="pb-1 text-sm text-corridor-muted">
            {score.band} {score.trend && <span>· {TREND_ARROW[score.trend]} {score.trend}</span>}
          </div>
        )}
      </div>

      {score.value == null && (
        <p className="text-xs text-corridor-muted">
          Not enough India-related coverage of {country.name} yet to score this pair.
        </p>
      )}

      {/* Sparkline */}
      {spark.length >= 2 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">30-day trend</div>
          <MicroSparkline points={spark} height={44} />
        </div>
      )}

      {/* Channel bars */}
      {channelEntries.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <div className="text-[10px] uppercase tracking-wide text-corridor-muted">Pressure channels</div>
          {channelEntries.map(([key, value]) => (
            <ScoreBar key={key} label={channelLabel(key)} value={value} />
          ))}
        </div>
      )}

      {/* Corridors */}
      {corridors.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">Corridors implicated</div>
          <div className="flex flex-wrap gap-1.5">
            {corridors.map((c) => (
              <span key={c.id} className="rounded bg-white/10 px-2 py-0.5 text-[11px] text-white/80">
                {c.name}
                {c.risk_7ma != null && <span className="ml-1 text-corridor-muted">{c.risk_7ma}</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Market */}
      {market?.index && (
        <div className="text-xs text-corridor-muted">
          Market: {market.index}
          {market.last != null ? (
            <span className="ml-1 text-white">{market.last}</span>
          ) : (
            <span className="ml-1">—</span>
          )}
        </div>
      )}

      {/* Country facts */}
      {facts && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">Country facts</div>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-white/80">
            {facts.capital && (<><dt className="text-corridor-muted">Capital</dt><dd className="text-right">{facts.capital}</dd></>)}
            {facts.population != null && (<><dt className="text-corridor-muted">Population</dt><dd className="text-right">{fmtNum(facts.population)}</dd></>)}
            {facts.region && (<><dt className="text-corridor-muted">Region</dt><dd className="text-right">{facts.region}</dd></>)}
            {facts.income_level && (<><dt className="text-corridor-muted">Income</dt><dd className="text-right">{facts.income_level}</dd></>)}
          </dl>
        </div>
      )}

      {/* Macro indicators */}
      {macro && (macro.gdp_growth_pct != null || macro.inflation_pct != null || macro.unemployment_pct != null) && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">
            Economic indicators <span className="normal-case">(World Bank)</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'GDP growth', v: macro.gdp_growth_pct, y: macro.gdp_growth_pct_year },
              { label: 'Inflation', v: macro.inflation_pct, y: macro.inflation_pct_year },
              { label: 'Unemployment', v: macro.unemployment_pct, y: macro.unemployment_pct_year },
            ].map((m) => (
              <div key={m.label} className="rounded bg-white/5 py-2">
                <div className="text-sm font-semibold text-white">{m.v != null ? `${m.v}%` : '—'}</div>
                <div className="text-[9px] text-corridor-muted">{m.label}{m.y ? ` '${String(m.y).slice(2)}` : ''}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Energy mix */}
      {energy?.mix && Object.keys(energy.mix).length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">
            Electricity mix <span className="normal-case">(OWID/Ember {energy.year})</span>
          </div>
          <div className="mb-2 flex h-2.5 overflow-hidden rounded">
            <div className="bg-corridor-alert" style={{ width: `${energy.fossil_pct ?? 0}%` }} title={`Fossil ${energy.fossil_pct}%`} />
            <div className="bg-corridor-clear" style={{ width: `${energy.renewable_pct ?? 0}%` }} title={`Renewable ${energy.renewable_pct}%`} />
            <div className="bg-corridor-watch" style={{ width: `${energy.nuclear_pct ?? 0}%` }} title={`Nuclear ${energy.nuclear_pct}%`} />
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-white/70">
            <span><span className="text-corridor-alert">■</span> Fossil {energy.fossil_pct}%</span>
            <span><span className="text-corridor-clear">■</span> Renewable {energy.renewable_pct}%</span>
            <span><span className="text-corridor-watch">■</span> Nuclear {energy.nuclear_pct}%</span>
          </div>
        </div>
      )}

      {/* Ports */}
      {ports && ports.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">
            Top ports <span className="normal-case">(IMF PortWatch)</span>
          </div>
          <table className="w-full text-[11px] text-white/80">
            <thead className="text-corridor-muted">
              <tr><th className="text-left font-normal">Port</th><th className="text-right font-normal">Vessels</th><th className="text-right font-normal">Tankers</th><th className="text-right font-normal">Imp%</th></tr>
            </thead>
            <tbody>
              {ports.slice(0, 5).map((p, i) => (
                <tr key={i}>
                  <td className="truncate pr-2" title={p.name ?? ''}>{p.name}</td>
                  <td className="text-right tabular-nums">{p.vessels?.toLocaleString() ?? '—'}</td>
                  <td className="text-right tabular-nums">{p.tankers?.toLocaleString() ?? '—'}</td>
                  <td className="text-right tabular-nums">{p.import_share ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Country news */}
      {top_events && top_events.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">Recent news</div>
          <ul className="space-y-1.5">
            {top_events.map((e, i) => (
              <li key={i} className="text-xs leading-snug">
                <a href={e.link} target="_blank" rel="noreferrer" className="text-white/80 hover:text-white">
                  {e.title}
                </a>
                {e.source && <span className="ml-1 text-corridor-muted">· {e.source}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* AI brief */}
      {summary && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-corridor-muted">Intelligence brief</div>
          <p className="text-sm leading-relaxed text-white/85">{summary}</p>
        </div>
      )}
    </div>
  )
}
