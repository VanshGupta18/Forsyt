// Quality page's "Proven checks" section: plain-English cards for the
// headline-tier validation checks (via lib/qualityPlain.ts's translations),
// hidden entirely if none are available yet.
import type { QualityCheck, QualityReport } from '../../lib/api'
import { plainCheckExplainer, plainCheckTitle, STATUS_PLAIN } from '../../lib/qualityPlain'
import QualityPassBadge from './QualityPassBadge'

type Props = {
  checks: QualityCheck[]
  summary: QualityReport['summary']
}

export default function HeadlineTrustCards({ checks, summary }: Props) {
  const headline = summary.headline ?? {
    checks_total: summary.checks_total,
    checks_passing: summary.checks_passing,
    overall_status: summary.overall_status,
  }

  const headlineChecks = checks.filter((c) => c.tier === 'headline' && c.status !== 'na')

  if (!headlineChecks.length) {
    return (
      <p className="text-sm text-corridor-muted corridor-panel p-4">
        Key benchmark checks will appear here once validation has been run on the current index.
      </p>
    )
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <span className="corridor-kicker">Proven checks</span>
          <p className="text-sm text-corridor-muted mt-1">
            {headline.checks_passing} of {headline.checks_total} key checks passing
          </p>
        </div>
        <QualityPassBadge
          status={
            headline.overall_status === 'pass'
              ? 'pass'
              : headline.overall_status === 'fail'
                ? 'fail'
                : 'warn'
          }
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {headlineChecks.map((check) => (
          <article key={check.id} className="corridor-panel p-4 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm text-white font-medium leading-snug">{plainCheckTitle(check)}</h3>
              <QualityPassBadge status={check.status} />
            </div>
            <p className="text-xs text-corridor-muted leading-relaxed">{plainCheckExplainer(check)}</p>
            <div className="flex justify-between items-baseline pt-1 border-t border-white/5">
              <span className="corridor-score text-lg text-white">{check.value ?? '—'}</span>
              <span className="text-[10px] text-corridor-muted">{STATUS_PLAIN[check.status]}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
