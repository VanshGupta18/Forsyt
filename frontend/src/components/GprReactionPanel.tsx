// Macro page panel: "how markets reacted to geopolitical-risk spikes".
// Top: event study — the average path of one asset from 5 trading days before
// to 20 after the biggest global GPR spikes, with the middle-50% band (inline
// SVG; one line + band doesn't need the canvas pipeline). Bottom: impulse
// responses — the move per 1-SD GPR jump over 1/5/20 days, with significant
// ones highlighted. Explanation of the channels, not a forecast.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchGprReaction, type GprReactionIrf } from '../lib/api'
import { queryKeys } from '../lib/queryClient'
import { CHART_PALETTE } from '../lib/chartCanvas'

const W = 600
const H = 220
const PAD = { l: 44, r: 12, t: 12, b: 26 }
// Flask sorts JSON keys alphabetically; show assets in reading order instead.
const ASSET_ORDER = ['NIFTY', 'SP500', 'BRENT', 'USDINR', 'INDIAVIX']

function fmt(v: number | null | undefined, unit: string) {
  if (v == null) return '—'
  const s = `${v > 0 ? '+' : ''}${v.toFixed(2)}`
  return unit === 'pts' ? `${s} pts` : `${s}%`
}

function irfCell(r: GprReactionIrf | undefined) {
  if (!r) return <td className="px-2 py-1 text-right text-corridor-muted">—</td>
  return (
    <td
      className={`px-2 py-1 text-right tabular-nums ${r.significant ? 'text-white font-semibold' : 'text-corridor-muted'}`}
      title={`90% range ${fmt(r.ci_low, r.unit)} to ${fmt(r.ci_high, r.unit)} · t=${r.t} · n=${r.n}`}
    >
      {fmt(r.effect, r.unit)}
      {r.significant ? ' *' : ''}
    </td>
  )
}

export default function GprReactionPanel() {
  const { data, error, isLoading } = useQuery({
    queryKey: queryKeys.gprReaction,
    queryFn: fetchGprReaction,
    staleTime: 6 * 60 * 60 * 1000,
  })
  const [asset, setAsset] = useState('NIFTY')
  const [regime, setRegime] = useState<'all' | 'elevated'>('all')

  if (isLoading) return <div className="corridor-panel p-4 text-sm text-corridor-muted">Loading market reaction study…</div>
  if (error || !data?.path) return null

  const days = data.path.days
  const series = data.path.series[asset] ?? Object.values(data.path.series)[0]
  const vals = [...series.p25, ...series.p75, ...series.mean, 0].filter((v): v is number => v != null)
  const lo = Math.min(...vals)
  const hi = Math.max(...vals)
  const x = (d: number) => PAD.l + ((d - days[0]) / (days[days.length - 1] - days[0])) * (W - PAD.l - PAD.r)
  const y = (v: number) => PAD.t + ((hi - v) / (hi - lo || 1)) * (H - PAD.t - PAD.b)
  const pts = (arr: (number | null)[]) =>
    days.flatMap((d, i) => (arr[i] == null ? [] : [`${x(d)},${y(arr[i] as number)}`]))
  const band = [...pts(series.p75), ...pts(series.p25).reverse()].join(' ')

  const irf = data.irf.filter((r) => r.regime === regime)
  const assets = Object.keys(data.path.series).sort((a, b) => ASSET_ORDER.indexOf(a) - ASSET_ORDER.indexOf(b))
  const find = (a: string, h: number) => irf.find((r) => r.asset === a && r.h === h)
  const findings = data.irf.filter((r) => r.regime === 'all' && r.significant)

  return (
    <section className="corridor-panel p-4 flex flex-col gap-4">
      <div>
        <p className="corridor-kicker">Market reaction</p>
        <h2 className="corridor-headline mt-1">How markets reacted to geopolitical-risk spikes</h2>
        <p className="text-xs text-corridor-muted mt-1 max-w-3xl">
          Average move around the {data.events.length} largest jumps in global geopolitical risk since 2008
          ({data.gpr_source}, through {data.gpr_as_of}). Day 0 is the spike; moves are measured from the close
          the day before. Explains how risk travels through markets — not a forecast.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {assets.map((a) => (
          <button
            key={a}
            type="button"
            onClick={() => setAsset(a)}
            className={`text-[11px] px-2 py-1 ${a === asset ? 'bg-white/15 text-white' : 'bg-white/5 text-corridor-muted'}`}
          >
            {data.path.series[a].label}
          </button>
        ))}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
        aria-label={`${series.label} average move around geopolitical-risk spikes`}>
        <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} stroke={CHART_PALETTE.axis} strokeDasharray="3 3" />
        <line x1={x(0)} x2={x(0)} y1={PAD.t} y2={H - PAD.b} stroke={CHART_PALETTE.gpr} strokeOpacity={0.6} />
        <text x={x(0) + 4} y={PAD.t + 10} fill={CHART_PALETTE.gpr} fontSize="10">spike</text>
        <polygon points={band} fill={CHART_PALETTE.primary} fillOpacity={0.15} />
        <polyline points={pts(series.mean).join(' ')} fill="none" stroke={CHART_PALETTE.primary} strokeWidth={2} />
        {[lo, 0, hi].map((v) => (
          <text key={v} x={PAD.l - 6} y={y(v) + 3} textAnchor="end" fill={CHART_PALETTE.axis} fontSize="10">
            {fmt(v, series.unit)}
          </text>
        ))}
        {[-5, 0, 5, 10, 20].map((d) => (
          <text key={d} x={x(d)} y={H - 8} textAnchor="middle" fill={CHART_PALETTE.axis} fontSize="10">
            {d > 0 ? `+${d}d` : `${d}d`}
          </text>
        ))}
      </svg>
      <p className="text-[11px] text-corridor-muted -mt-2">
        Line: average · shaded: middle 50% of episodes. After 5 days: {fmt(series.mean[days.indexOf(5)], series.unit)},
        after 20 days: {fmt(series.mean[days.indexOf(20)], series.unit)}.
      </p>

      <div>
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <p className="corridor-kicker">Move per 1-SD jump in geopolitical risk</p>
          <div className="flex gap-1">
            {(['all', 'elevated'] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRegime(r)}
                className={`text-[11px] px-2 py-1 ${r === regime ? 'bg-white/15 text-white' : 'bg-white/5 text-corridor-muted'}`}
              >
                {r === 'all' ? 'All days' : 'When risk already elevated'}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-corridor-muted">
                <th className="px-2 py-1 text-left font-normal">Asset</th>
                <th className="px-2 py-1 text-right font-normal">1 day</th>
                <th className="px-2 py-1 text-right font-normal">5 days</th>
                <th className="px-2 py-1 text-right font-normal">20 days</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => (
                <tr key={a} className="border-t border-white/5">
                  <td className="px-2 py-1">{data.path.series[a].label}</td>
                  {irfCell(find(a, 1))}
                  {irfCell(find(a, 5))}
                  {irfCell(find(a, 20))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-corridor-muted mt-2">
          * statistically significant (90% range excludes zero), controlling for recent NIFTY returns, volatility
          and India VIX. Hover a cell for its range.
          {findings.length === 0 && ' No channel is significant on all days.'}
        </p>
      </div>
    </section>
  )
}
