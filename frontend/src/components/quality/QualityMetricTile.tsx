import type { QualityCheckStatus } from '../../lib/api'
import QualityPassBadge from './QualityPassBadge'

type Props = {
  label: string
  value: string | number
  status?: QualityCheckStatus | null
  unit?: string
}

export default function QualityMetricTile({ label, value, status, unit }: Props) {
  const valueClass =
    status === 'pass'
      ? 'text-corridor-clear'
      : status === 'fail'
        ? 'text-corridor-alert'
        : status === 'warn'
          ? 'text-corridor-watch'
          : 'text-white'

  return (
    <div className="corridor-panel p-4 flex flex-col gap-2 min-w-[140px] flex-1">
      <span className="corridor-kicker text-[10px]">{label}</span>
      <span className={`corridor-score text-2xl ${valueClass}`}>
        {value}
        {unit && <span className="text-sm text-corridor-muted ml-1">{unit}</span>}
      </span>
      {status && status !== 'na' && (
        <QualityPassBadge status={status} className="w-fit" />
      )}
    </div>
  )
}
