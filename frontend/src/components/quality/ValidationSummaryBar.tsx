import type { QualityReport } from '../../lib/api'

type Props = {
  summary: QualityReport['summary']
}

const OVERALL_LABEL: Record<string, string> = {
  pass: 'Key checks look good',
  warn: 'Some checks need review',
  fail: 'Some checks need attention',
}

export default function ValidationSummaryBar({ summary }: Props) {
  const headline = summary.headline ?? summary
  const pct =
    headline.checks_total > 0
      ? Math.round((headline.checks_passing / headline.checks_total) * 100)
      : 0

  const badgeStatus =
    headline.overall_status === 'pass' ? 'pass' : headline.overall_status === 'fail' ? 'fail' : 'warn'

  return (
    <div className="corridor-panel p-4 flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={`w-2 h-2 rounded-full shrink-0 ${
            badgeStatus === 'pass'
              ? 'bg-corridor-clear'
              : badgeStatus === 'fail'
                ? 'bg-corridor-alert'
                : 'bg-corridor-watch'
          }`}
        />
        <div>
          <p className="font-body-md text-white">{OVERALL_LABEL[headline.overall_status] ?? 'Validation status'}</p>
          <p className="text-xs text-corridor-muted">
            {headline.checks_passing} of {headline.checks_total} key checks passing
          </p>
        </div>
      </div>
      <div className="flex-1 min-w-[120px]">
        <div className="flex justify-between text-xs text-corridor-muted mb-1">
          <span>Key checks</span>
          <span className="corridor-score text-white">{pct}%</span>
        </div>
        <div className="h-1.5 bg-white/10 overflow-hidden">
          <div className="h-full bg-corridor-clear transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  )
}
