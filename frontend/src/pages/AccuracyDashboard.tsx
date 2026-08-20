import { useCallback, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ApiErrorBanner from '../components/ApiErrorBanner'
import LoadingSkeleton from '../components/LoadingSkeleton'
import DataArchitectureDiagram from '../components/quality/DataArchitectureDiagram'
import HeadlineTrustCards from '../components/quality/HeadlineTrustCards'
import LiveStatusStrip from '../components/quality/LiveStatusStrip'
import MethodologyPipeline from '../components/quality/MethodologyPipeline'
import QualityCheckTable from '../components/quality/QualityCheckTable'
import StaleDataBanner from '../components/quality/StaleDataBanner'
import ValidationSummaryBar from '../components/quality/ValidationSummaryBar'
import ValidationVizPanel from '../components/quality/ValidationVizPanel'
import { fetchPageQuality } from '../lib/api'
import { queryKeys } from '../lib/queryClient'
import {
  QUALITY_EYEBROW,
  QUALITY_SUBTITLE,
  QUALITY_TITLE,
  SECTION_HOW_BUILT,
  SECTION_HOW_BUILT_SUB,
  SECTION_TECHNICAL,
  SECTION_TECHNICAL_SUB,
  TOGGLE_HIDE_TECHNICAL,
  TOGGLE_SHOW_TECHNICAL,
  qualityStatusLine,
} from '../lib/qualityCopy'

function FeedHealthTable({
  feedHealth,
}: {
  feedHealth: Record<
    string,
    { consecutive_failures?: number; last_success?: string | null; last_error?: string | null }
  >
}) {
  const [open, setOpen] = useState(false)
  const entries = Object.entries(feedHealth)
  if (!entries.length) return null

  return (
    <div className="corridor-panel overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 text-left corridor-btn bg-transparent hover:bg-[#111111]"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="corridor-kicker">News feed details ({entries.length})</span>
        <span className="material-symbols-outlined text-corridor-muted text-lg">
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>
      {open && (
        <div className="overflow-x-auto border-t border-white/5">
          <table className="w-full text-sm min-w-[480px]">
            <thead className="text-corridor-muted border-b border-white/10">
              <tr>
                <th className="text-left p-3 font-medium">Source</th>
                <th className="text-left p-3 font-medium">Failures</th>
                <th className="text-left p-3 font-medium">Last success</th>
                <th className="text-left p-3 font-medium">Last error</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([name, h]) => (
                <tr key={name} className="border-b border-white/5">
                  <td className="p-3 text-white">{name}</td>
                  <td
                    className={`p-3 corridor-score ${(h.consecutive_failures ?? 0) > 0 ? 'text-corridor-alert' : 'text-corridor-clear'}`}
                  >
                    {h.consecutive_failures ?? 0}
                  </td>
                  <td className="p-3 text-corridor-muted text-xs">
                    {h.last_success ? new Date(h.last_success).toLocaleString() : '—'}
                  </td>
                  <td className="p-3 text-corridor-muted text-xs truncate max-w-xs">{h.last_error ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function AccuracyDashboard() {
  const queryClient = useQueryClient()
  const [refreshing, setRefreshing] = useState(false)
  const [technicalOpen, setTechnicalOpen] = useState(false)

  const { data, error, isLoading, refetch, isError } = useQuery({
    queryKey: queryKeys.quality(false),
    queryFn: () => fetchPageQuality(false),
    refetchOnMount: 'always',
  })

  const load = useCallback(
    (refresh = false) => {
      if (refresh) {
        setRefreshing(true)
        fetchPageQuality(true)
          .then((report) => {
            queryClient.setQueryData(queryKeys.quality(false), report)
          })
          .finally(() => setRefreshing(false))
      } else {
        void refetch()
      }
    },
    [queryClient, refetch],
  )

  return (
    <div className="corridor-page max-w-container-max mx-auto px-margin-page py-stack-lg flex flex-col gap-stack-lg">
      <section className="space-y-4 max-w-3xl">
        <span className="eyebrow-badge">
          <span className="eyebrow-dot" />
          {QUALITY_EYEBROW}
        </span>
        <h1 className="corridor-display font-headline-lg text-headline-lg">{QUALITY_TITLE}</h1>
        <p className="font-body-md text-corridor-muted">{QUALITY_SUBTITLE}</p>
        {data && (
          <p className="text-xs text-corridor-muted">
            {qualityStatusLine(data.as_of.gpr_latest_date, data.as_of.pipeline_last_run)}
            {data.report_meta?.live_gpr_source && ` · source: ${data.report_meta.live_gpr_source}`}
            {' · '}
            Generated {new Date(data.generated_at).toLocaleString()}
          </p>
        )}
      </section>

      {isError && !data && error instanceof Error && (
        <ApiErrorBanner
          message={`Could not load quality report (${error.message}). If you just restarted the API, retry now.`}
          onRetry={() => void refetch()}
        />
      )}
      {isLoading && !data && <LoadingSkeleton lines={4} />}

      {data && (
        <>
          {data.report_meta && <StaleDataBanner reportMeta={data.report_meta} />}
          <ValidationSummaryBar summary={data.summary} />
          <LiveStatusStrip data={data} />
          <HeadlineTrustCards checks={data.checks} summary={data.summary} />

          <section className="space-y-4">
            <div>
              <span className="corridor-kicker">{SECTION_HOW_BUILT}</span>
              <p className="text-sm text-corridor-muted mt-1">{SECTION_HOW_BUILT_SUB}</p>
            </div>
            <MethodologyPipeline />
            <DataArchitectureDiagram />
          </section>

          <section className="space-y-4 border-t border-white/5 pt-6">
            <button
              type="button"
              className="corridor-btn px-4 py-2.5 text-sm flex items-center gap-2"
              onClick={() => setTechnicalOpen((o) => !o)}
              aria-expanded={technicalOpen}
            >
              {technicalOpen ? TOGGLE_HIDE_TECHNICAL : TOGGLE_SHOW_TECHNICAL}
              <span className="material-symbols-outlined text-base">
                {technicalOpen ? 'expand_less' : 'expand_more'}
              </span>
            </button>

            {technicalOpen && (
              <div className="space-y-6 pt-2">
                <div>
                  <span className="corridor-kicker">{SECTION_TECHNICAL}</span>
                  <p className="text-sm text-corridor-muted mt-1">{SECTION_TECHNICAL_SUB}</p>
                  {data.report_meta?.validation_artifacts_as_of && (
                    <p className="text-xs text-corridor-muted mt-1">
                      Offline benchmarks last run{' '}
                      {new Date(data.report_meta.validation_artifacts_as_of).toLocaleString()}
                    </p>
                  )}
                </div>
                <ValidationVizPanel checks={data.checks} summary={data.summary} />
                <QualityCheckTable checks={data.checks} onRefresh={() => load(true)} refreshing={refreshing} />
                {data.pipeline.ingestion?.feed_health &&
                  Object.keys(data.pipeline.ingestion.feed_health).length > 0 && (
                    <FeedHealthTable feedHealth={data.pipeline.ingestion.feed_health} />
                  )}
              </div>
            )}
          </section>

          <footer className="border-t border-white/5 pt-6 space-y-2">
            <p className="text-xs text-corridor-muted">{data.disclaimer}</p>
            <p className="text-xs text-corridor-muted/70">
              Validation artifacts: gpr_index/outputs/validation/
            </p>
          </footer>
        </>
      )}
    </div>
  )
}
