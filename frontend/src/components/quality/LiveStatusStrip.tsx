// Quality page's "Right now" section: a row of QualityMetricTiles answering
// "is data flowing, fresh, and ready to use" (last update, feed health,
// article counts, NLP coverage).
import type { QualityReport } from '../../lib/api'
import QualityMetricTile from './QualityMetricTile'

type Props = {
  data: QualityReport
}

export default function LiveStatusStrip({ data }: Props) {
  const ingestion = data.pipeline.ingestion
  const nlp = data.pipeline.nlp
  const status = data.status
  const health = data.health

  const feedsHealthy =
    ingestion?.sources_unhealthy === 0 && (ingestion?.sources_total ?? 0) > 0
  const lastUpdate =
    data.as_of.gpr_latest_date?.slice(0, 10) ??
    status?.latest_dates?.gpr ??
    health?.gpr_latest_date?.slice(0, 10) ??
    '—'

  return (
    <section className="space-y-3">
      <div>
        <span className="corridor-kicker">Right now</span>
        <p className="text-sm text-corridor-muted mt-1">Is data flowing, fresh, and ready to use?</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <QualityMetricTile
          label="Last risk update"
          value={lastUpdate}
          status={status?.stale_warning || health?.stale_warning ? 'warn' : 'pass'}
        />
        <QualityMetricTile
          label="News feeds"
          value={
            ingestion?.sources_total
              ? `${ingestion.sources_healthy}/${ingestion.sources_total} OK`
              : '—'
          }
          status={feedsHealthy ? 'pass' : ingestion?.sources_unhealthy ? 'fail' : undefined}
        />
        <QualityMetricTile label="Articles indexed" value={ingestion?.total_articles ?? '—'} />
        <QualityMetricTile
          label="Articles analysed"
          value={nlp?.coverage_pct != null ? `${nlp.coverage_pct}%` : '—'}
          status={
            nlp?.coverage_pct != null ? (nlp.coverage_pct >= 95 ? 'pass' : 'fail') : undefined
          }
        />
      </div>
      {(status?.stale_warning || health?.stale_warning) && (
        <p className="text-xs text-corridor-watch">{status?.stale_warning ?? health?.stale_warning}</p>
      )}
    </section>
  )
}
