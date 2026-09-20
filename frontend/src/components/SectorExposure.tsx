// Interactive sector-exposure view: a donut (part-to-whole by weight) + a
// legend/table with exact numbers. Click a slice or a row to filter to that
// sector's holdings. Categorical colors are the dataviz skill's validated
// dark-surface palette, assigned by sector identity (never by rank) so the
// colors are stable across re-runs.
import { useState } from 'react'
import type { PortfolioHolding, PortfolioSector } from '../lib/api'

const SECTOR_COLORS: Record<string, string> = {
  'Financial Services': '#3987e5', // blue
  Technology: '#d95926', // orange
  Energy: '#199e70', // aqua
  'Consumer Cyclical': '#c98500', // yellow
  'Consumer Defensive': '#d55181', // magenta
  Healthcare: '#008300', // green
  'Basic Materials': '#9085e9', // violet
  Utilities: '#e66767', // red
  Industrials: '#6da7ec', // blue-light (rare overflow)
  'Communication Services': '#f0a24b', // orange-light (rare overflow)
  'Real Estate': '#5bc6a0', // aqua-light (rare overflow)
}
const OTHER = '#737373'
const colorFor = (sector: string) => SECTOR_COLORS[sector] ?? OTHER

export default function SectorExposure({
  sectors,
  holdings,
}: {
  sectors: PortfolioSector[]
  holdings: PortfolioHolding[]
}) {
  const [sel, setSel] = useState<string | null>(null)

  const total = sectors.reduce((s, r) => s + Math.max(r.weight, 0), 0) || 1
  const size = 168
  const r = 62
  const sw = 24
  const c = size / 2
  const circ = 2 * Math.PI * r

  let acc = 0
  const segs = sectors
    .filter((s) => s.weight > 0)
    .map((s) => {
      const frac = s.weight / total
      const seg = { sector: s.sector, color: colorFor(s.sector), len: frac * circ, offset: acc * circ, frac }
      acc += frac
      return seg
    })

  const selRow = sectors.find((s) => s.sector === sel) ?? null
  const selHoldings = sel
    ? holdings.filter((h) => h.sector === sel).sort((a, b) => b.weight - a.weight)
    : []
  const toggle = (s: string) => setSel((cur) => (cur === s ? null : s))

  return (
    <div>
      <div className="text-xs text-gray-500 uppercase mb-3">
        Exposure by sector <span className="text-gray-600 normal-case">· click a slice or row</span>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 items-start">
        {/* Donut */}
        <div className="relative shrink-0 mx-auto sm:mx-0" style={{ width: size, height: size }}>
          <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label="Sector weight donut">
            <g transform={`rotate(-90 ${c} ${c})`}>
              {segs.map((seg) => {
                const dim = sel !== null && sel !== seg.sector
                return (
                  <circle
                    key={seg.sector}
                    cx={c}
                    cy={c}
                    r={r}
                    fill="none"
                    stroke={seg.color}
                    strokeWidth={dim ? sw - 6 : sw}
                    strokeDasharray={`${seg.len} ${circ - seg.len}`}
                    strokeDashoffset={-seg.offset}
                    opacity={dim ? 0.35 : 1}
                    style={{ cursor: 'pointer', transition: 'opacity .15s, stroke-width .15s' }}
                    onClick={() => toggle(seg.sector)}
                  >
                    <title>{`${seg.sector} · ${Math.round(seg.frac * 100)}%`}</title>
                  </circle>
                )
              })}
            </g>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-4">
            {selRow ? (
              <>
                <div className="text-[10px] text-gray-500 uppercase leading-tight">{selRow.sector}</div>
                <div className="text-2xl font-bold text-white">{Math.round(selRow.weight * 100)}%</div>
                <div className="text-[10px]" style={{ color: selRow.contribution < 0 ? '#00c853' : '#fff' }}>
                  {selRow.contribution > 0 ? '+' : ''}
                  {selRow.contribution} risk
                </div>
              </>
            ) : (
              <>
                <div className="text-[10px] text-gray-500 uppercase">Sectors</div>
                <div className="text-2xl font-bold text-white">{segs.length}</div>
              </>
            )}
          </div>
        </div>

        {/* Legend / table (exact numbers) */}
        <div className="flex-1 min-w-0 w-full">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase border-b border-white/10">
                <th className="pb-1 text-left">Sector</th>
                <th className="pb-1 text-right">Weight</th>
                <th className="pb-1 text-right">Risk</th>
              </tr>
            </thead>
            <tbody>
              {sectors.map((s) => {
                const active = sel === s.sector
                return (
                  <tr
                    key={s.sector}
                    onClick={() => toggle(s.sector)}
                    className={`cursor-pointer border-b border-white/5 hover:bg-white/5 ${active ? 'bg-white/5' : ''}`}
                  >
                    <td className="py-1.5">
                      <span className="inline-flex items-center gap-2">
                        <span className="inline-block w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: colorFor(s.sector) }} />
                        {s.sector}
                      </span>
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{Math.round(s.weight * 100)}%</td>
                    <td className={`py-1.5 text-right tabular-nums ${s.contribution < 0 ? 'text-corridor-clear' : 'text-white'}`}>
                      {s.contribution > 0 ? '+' : ''}
                      {s.contribution}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected sector → its holdings */}
      {sel && (
        <div className="mt-3 bg-[#0d0d0d] border border-white/5 rounded p-3">
          <div className="text-[10px] text-gray-500 uppercase mb-2 flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: colorFor(sel) }} />
            {sel} — {selHoldings.length} holding{selHoldings.length !== 1 ? 's' : ''}
          </div>
          {selHoldings.length ? (
            <table className="w-full text-sm">
              <tbody className="divide-y divide-white/5">
                {selHoldings.map((h) => (
                  <tr key={h.ticker}>
                    <td className="py-1">{h.ticker}</td>
                    <td className="py-1 text-right tabular-nums text-gray-400">{Math.round(h.weight * 100)}%</td>
                    <td className={`py-1 text-right tabular-nums ${h.contribution < 0 ? 'text-corridor-clear' : 'text-white'}`}>
                      {h.contribution > 0 ? '+' : ''}
                      {h.contribution}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-xs text-gray-500">No holdings in this sector.</div>
          )}
        </div>
      )}
    </div>
  )
}
