import type { QualityReport } from '../../lib/api'

type Props = {
  reportMeta: QualityReport['report_meta']
}

export default function StaleDataBanner({ reportMeta }: Props) {
  if (!reportMeta?.is_stale) return null
  const validated = reportMeta.validation_artifacts_as_of
    ? new Date(reportMeta.validation_artifacts_as_of).toLocaleDateString()
    : 'unknown date'
  return (
    <div className="corridor-panel border-l-2 border-corridor-watch px-4 py-3 flex gap-3 items-start">
      <span className="material-symbols-outlined text-corridor-watch text-lg shrink-0">info</span>
      <div className="space-y-1">
        <p className="text-sm text-white font-medium">Benchmarks need re-validation</p>
        <p className="text-xs text-corridor-muted leading-relaxed">
          {reportMeta.stale_reason ??
            `Offline checks were last run ${validated}. The live index has been updated since then.`}
        </p>
      </div>
    </div>
  )
}
