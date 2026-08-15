import type { DualSignalPayload } from '../lib/api'

type Props = {
  analog?: DualSignalPayload['historical_analog'] | null
}

export default function HistoricalAnalogPanel({ analog }: Props) {
  const sampleDays = analog?.sample_days ?? 0
  const thin = sampleDays > 0 && sampleDays < 5

  if (sampleDays < 3) return null

  return (
    <div className="corridor-panel p-4 flex flex-col gap-3 h-full">
      <div>
        <p className="corridor-kicker">Historical context</p>
        <h2 className="corridor-headline mt-1">When news risk looked like this before</h2>
      </div>

      <p className="text-sm text-corridor-muted">{analog?.query}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="bg-[#0d0d0d] p-3">
          <p className="corridor-kicker text-[9px]">Sample days</p>
          <p className="corridor-score text-xl text-white">{sampleDays}</p>
        </div>
        <div className="bg-[#0d0d0d] p-3">
          <p className="corridor-kicker text-[9px]">Median 5d NIFTY return</p>
          <p className="corridor-score text-xl text-white">
            {analog?.nifty_return_median != null ? `${analog.nifty_return_median}%` : '—'}
          </p>
        </div>
        <div className="bg-[#0d0d0d] p-3 col-span-2 sm:col-span-1">
          <p className="corridor-kicker text-[9px]">Median 5d vol</p>
          <p className="corridor-score text-xl text-white">
            {analog?.nifty_vol_median != null ? `${analog.nifty_vol_median}%` : '—'}
          </p>
        </div>
      </div>

      {thin && (
        <p className="text-xs text-corridor-watch border-l-2 border-[var(--corridor-accent-watch)] pl-3">
          Early index — only {sampleDays} similar day{sampleDays === 1 ? '' : 's'} so far. Treat medians as directional, not precise forecasts.
        </p>
      )}

      {!thin && sampleDays >= 5 && (
        <p className="text-xs text-corridor-muted">
          Past similar news-risk levels — median outcomes, not a prediction for your SIP.
        </p>
      )}

      {(analog?.notable_events?.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-2">
          {analog!.notable_events!.map((ev) => (
            <span
              key={ev}
              className="text-[10px] uppercase font-semibold px-2 py-1 bg-white/5 text-corridor-muted"
            >
              {ev}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
