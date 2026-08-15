import { useState } from 'react'
import type { DualSignalPayload } from '../lib/api'

type Props = {
  dual: DualSignalPayload | null
  indicators: { trailing_vol_22d?: number | null; return_7d_pct?: number | null } | null
  volUnavailable: boolean
}

export default function SignalDetailsAccordion({ dual, indicators, volUnavailable }: Props) {
  const [open, setOpen] = useState(false)
  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility

  const rows: Array<{ label: string; value: string }> = [
    { label: 'GPR 7d MA', value: geo?.gpr_7ma != null ? String(geo.gpr_7ma) : '—' },
    { label: 'GPR 30d MA', value: geo?.gpr_30ma != null ? String(geo.gpr_30ma) : '—' },
    {
      label: 'Trailing vol (22d)',
      value:
        vol?.trailing_vol_22d != null
          ? `${vol.trailing_vol_22d}%`
          : indicators?.trailing_vol_22d != null
            ? `${indicators.trailing_vol_22d}%`
            : '—',
    },
    {
      label: 'High-vol probability',
      value:
        !volUnavailable && vol?.high_vol_prob != null
          ? `${(vol.high_vol_prob * 100).toFixed(1)}%`
          : '—',
    },
    { label: 'Vol model', value: vol?.model ?? '—' },
    {
      label: 'Stress blend',
      value: '60% news risk percentile + 40% vol percentile',
    },
  ]

  return (
    <div className="corridor-panel">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 text-left corridor-btn bg-transparent hover:bg-[#111111]"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="corridor-kicker">Signal details & methodology</span>
        <span className="material-symbols-outlined text-corridor-muted text-lg">
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-0 text-sm border-t border-white/5">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex justify-between gap-4 py-2 border-b border-white/5 last:border-0"
            >
              <span className="text-corridor-muted shrink-0">{row.label}</span>
              <span className="text-white text-right tabular-nums">{row.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
