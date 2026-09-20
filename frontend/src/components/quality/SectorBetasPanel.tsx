// Sector-sensitivity fitted betas — a trained-model artifact (weekly sector
// returns regressed on GPR/oil/INR shocks). Lives on the Quality page's
// technical section, next to the vol-model explainability panel, since it's
// methodology detail rather than a user-facing portfolio view.
import { useQuery } from '@tanstack/react-query'
import { fetchSectorBetas, type SectorBeta } from '../../lib/api'

function tiltColor(tilt: 'headwind' | 'tailwind' | 'neutral'): string {
  if (tilt === 'headwind') return 'text-corridor-alert'
  if (tilt === 'tailwind') return 'text-corridor-clear'
  return 'text-gray-500'
}

function tiltWord(tilt: 'headwind' | 'tailwind' | 'neutral'): string {
  if (tilt === 'headwind') return 'Headwind'
  if (tilt === 'tailwind') return 'Tailwind'
  return 'Neutral'
}

function SectorBetaCard({ row }: { row: SectorBeta }) {
  return (
    <div className="bg-[#0d0d0d] p-4 border border-white/5">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-sm text-white font-medium">{row.sector}</span>
        <span className={`text-[10px] uppercase font-semibold shrink-0 ${tiltColor(row.tilt)}`}>
          {tiltWord(row.tilt)}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {row.channels.map((c) => (
          <span
            key={c.channel}
            className={`text-[11px] px-1.5 py-0.5 rounded bg-white/5 ${tiltColor(c.tilt)}`}
            title={`${c.label} loading`}
          >
            {c.label} {c.loading > 0 ? '+' : ''}{c.loading}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function SectorBetasPanel() {
  const { data: betas } = useQuery({
    queryKey: ['portfolio', 'sector-betas'],
    queryFn: fetchSectorBetas,
    staleTime: 1000 * 60 * 60,
  })

  return (
    <div className="corridor-panel p-4 space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <span className="corridor-kicker">Sector sensitivity · fitted betas</span>
          {betas?.betas_source && (
            <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded ${betas.betas_source === 'fitted' ? 'bg-corridor-clear/20 text-corridor-clear' : 'bg-white/10 text-gray-400'}`}>
              {betas.betas_source === 'fitted' ? 'trained' : 'prior'}
            </span>
          )}
        </div>
        <p className="text-sm text-corridor-muted mt-1">
          Estimated from ~19 years of weekly sector returns regressed on GPR, oil (Brent) and INR shocks.
          Each chip is the fitted loading on that channel — <span className="text-corridor-alert">+ = headwind</span>,{' '}
          <span className="text-corridor-clear">− = tailwind</span>. INR is the dominant channel.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {(betas?.sectors ?? []).map((row) => (
          <SectorBetaCard key={row.sector} row={row} />
        ))}
      </div>
    </div>
  )
}
