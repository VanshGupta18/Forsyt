import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export type MetricRow = {
  label: string
  value: string
  valueClass?: string
  href?: string
}

type Props = {
  title: string
  kicker: string
  spot?: {
    label: string
    price: string
    changePct?: number | null
    loading?: boolean
  }
  primary?: string
  primaryLabel?: string
  regime?: string
  regimeClass?: string
  rows: MetricRow[]
  highlighted?: boolean
  footer?: ReactNode
}

export default function MacroMetricTable({
  title,
  kicker,
  spot,
  primary,
  primaryLabel,
  regime,
  regimeClass = 'text-corridor-muted',
  rows,
  highlighted,
  footer,
}: Props) {
  return (
    <div
      className={`corridor-panel p-4 h-full flex flex-col gap-3 ${
        highlighted ? 'macro-signal-highlight' : ''
      }`}
    >
      <div>
        <p className="corridor-kicker">{kicker}</p>
        <h2 className="corridor-headline mt-1">{title}</h2>
      </div>

      {spot && (
        <div className="bg-[#0d0d0d] p-3">
          <p className="corridor-kicker">{spot.label}</p>
          <div className="corridor-score text-2xl text-white mt-1">
            {spot.loading ? '…' : spot.price}
          </div>
          {spot.changePct != null && !spot.loading && (
            <p
              className={`text-sm tabular-nums mt-1 ${
                spot.changePct >= 0 ? 'text-corridor-clear' : 'text-corridor-alert'
              }`}
            >
              {spot.changePct >= 0 ? '+' : ''}
              {spot.changePct}% today
            </p>
          )}
        </div>
      )}

      {primary != null && (
        <div className="bg-[#0d0d0d] p-3">
          {primaryLabel && <p className="corridor-kicker">{primaryLabel}</p>}
          <div className="flex items-end justify-between gap-2 mt-1">
            <span className="corridor-score text-3xl text-white">{primary}</span>
            {regime && <span className={`text-xs font-semibold uppercase ${regimeClass}`}>{regime}</span>}
          </div>
        </div>
      )}

      <div className="space-y-0 text-sm flex-1">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex justify-between gap-3 border-b border-white/5 py-2 last:border-0"
          >
            <span className="text-corridor-muted shrink-0">{row.label}</span>
            {row.href ? (
              <Link
                to={row.href}
                className="text-primary hover:underline text-right truncate corridor-headline text-sm"
              >
                {row.value}
              </Link>
            ) : (
              <span className={`tabular-nums text-right truncate ${row.valueClass ?? 'text-white'}`}>
                {row.value}
              </span>
            )}
          </div>
        ))}
      </div>

      {footer}
    </div>
  )
}
