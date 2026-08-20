import type { QualityCheckStatus } from '../../lib/api'
import { STATUS_PLAIN } from '../../lib/qualityPlain'

const STATUS_CLASS: Record<QualityCheckStatus, string> = {
  pass: 'bg-corridor-clear/15 text-corridor-clear border-corridor-clear/30',
  fail: 'bg-corridor-alert/15 text-corridor-alert border-corridor-alert/30',
  warn: 'bg-corridor-watch/15 text-corridor-watch border-corridor-watch/30',
  na: 'bg-white/5 text-corridor-muted border-white/10',
}

type Props = {
  status: QualityCheckStatus
  className?: string
  plain?: boolean
}

export default function QualityPassBadge({ status, className = '', plain = true }: Props) {
  const label = plain ? STATUS_PLAIN[status] : status.toUpperCase()
  return (
    <span
      className={`text-[10px] px-2 py-0.5 border font-medium tracking-wide whitespace-nowrap ${plain ? '' : 'uppercase'} ${STATUS_CLASS[status]} ${className}`}
    >
      {label}
    </span>
  )
}
