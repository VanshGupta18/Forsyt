import { Fragment, useMemo, useState } from 'react'
import type { QualityCheck } from '../../lib/api'
import { CATEGORY_INTROS, CHECK_CATEGORIES, type CheckCategoryFilter } from '../../lib/qualityCopy'
import { plainCategory, plainCheckExplainer, plainCheckTitle } from '../../lib/qualityPlain'
import QualityPassBadge from './QualityPassBadge'

type Props = {
  checks: QualityCheck[]
  onRefresh?: () => void
  refreshing?: boolean
}

function DetailTable({ detail }: { detail: Record<string, unknown> }) {
  const corridors = detail.corridors as
    | Array<{ corridor?: string; parent_correlation?: number; pass?: boolean }>
    | undefined
  if (corridors?.length) {
    return (
      <div className="overflow-x-auto mt-2 border-t border-white/5 pt-2">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-corridor-muted border-b border-white/5">
              <th className="text-left p-2 font-medium">Corridor</th>
              <th className="text-left p-2 font-medium">Parent r</th>
              <th className="text-left p-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {corridors.map((c) => (
              <tr key={c.corridor} className="border-b border-white/5">
                <td className="p-2 text-white">{c.corridor}</td>
                <td className="p-2 corridor-score">{c.parent_correlation}</td>
                <td className="p-2">
                  <QualityPassBadge status={c.pass ? 'pass' : 'fail'} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const cases = detail.cases as Array<{ label: string; pass: boolean }> | undefined
  if (cases?.length) {
    return (
      <div className="flex flex-wrap gap-2 mt-2 border-t border-white/5 pt-2">
        {cases.map((c) => (
          <span
            key={c.label}
            className={`text-xs px-2 py-1 border ${
              c.pass
                ? 'border-corridor-clear/30 text-corridor-clear'
                : 'border-corridor-alert/30 text-corridor-alert'
            }`}
          >
            {c.label}
          </span>
        ))}
      </div>
    )
  }

  const note = detail.note as string | undefined
  if (note) {
    return <p className="text-xs text-corridor-muted mt-2 border-t border-white/5 pt-2">{note}</p>
  }

  return null
}

export default function QualityCheckTable({ checks, onRefresh, refreshing }: Props) {
  const [filter, setFilter] = useState<CheckCategoryFilter>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const filtered = useMemo(
    () => (filter === 'all' ? checks : checks.filter((c) => c.category === filter)),
    [checks, filter],
  )

  const grouped = useMemo(() => {
    const cats =
      filter === 'all' ? (['pipeline', 'gpr', 'corridor', 'market', 'nlp'] as const) : [filter]
    return cats
      .map((cat) => ({
        category: cat,
        checks: filtered.filter((c) => c.category === cat),
      }))
      .filter((g) => g.checks.length > 0)
  }, [filtered, filter])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {CHECK_CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              type="button"
              className="corridor-tab px-3 py-1.5 text-xs"
              data-active={filter === cat.id}
              onClick={() => setFilter(cat.id)}
            >
              {cat.label}
            </button>
          ))}
        </div>
        {onRefresh && (
          <button
            type="button"
            className="corridor-btn px-3 py-1.5 text-xs disabled:opacity-50"
            onClick={onRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Recomputing…' : 'Recompute live checks'}
          </button>
        )}
      </div>

      {grouped.map(({ category, checks: groupChecks }) => (
        <section key={category} className="space-y-3">
          <div>
            <span className="corridor-kicker">{plainCategory(category)}</span>
            {CATEGORY_INTROS[category] && (
              <p className="text-sm text-corridor-muted mt-1 max-w-3xl">{CATEGORY_INTROS[category]}</p>
            )}
          </div>
          <div className="corridor-panel overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead className="text-corridor-muted border-b border-white/10 sticky top-0 bg-[#0a0a0a]">
                  <tr>
                    <th className="text-left p-3 font-medium w-[40%]">Check</th>
                    <th className="text-left p-3 font-medium">Value</th>
                    <th className="text-left p-3 font-medium">Threshold</th>
                    <th className="text-left p-3 font-medium">Status</th>
                    <th className="text-left p-3 font-medium">Validated</th>
                    <th className="p-3 w-8" aria-label="Expand" />
                  </tr>
                </thead>
                <tbody>
                  {groupChecks.map((check) => {
                    const isOpen = expanded === check.id
                    const hasDetail = check.detail && Object.keys(check.detail).length > 0
                    return (
                      <Fragment key={check.id}>
                        <tr className="border-b border-white/5 hover:bg-white/[0.02]">
                          <td className="p-3">
                            <p className="text-white">{plainCheckTitle(check)}</p>
                            <p className="text-xs text-corridor-muted mt-0.5">{plainCheckExplainer(check)}</p>
                            <p className="text-[10px] text-corridor-muted/50 mt-1">{check.title}</p>
                            {check.source?.path && (
                              <p className="text-[10px] text-corridor-muted/70 mt-1 font-mono truncate max-w-xs">
                                {check.source.path}
                              </p>
                            )}
                          </td>
                          <td className="p-3 corridor-score text-white">{check.value ?? '—'}</td>
                          <td className="p-3 text-corridor-muted text-xs">{check.threshold}</td>
                          <td className="p-3">
                            <QualityPassBadge status={check.status} />
                          </td>
                          <td className="p-3 text-xs text-corridor-muted whitespace-nowrap">
                            {check.validated_at
                              ? new Date(check.validated_at).toLocaleDateString()
                              : check.freshness === 'live'
                                ? 'Live'
                                : '—'}
                          </td>
                          <td className="p-3">
                            {hasDetail && (
                              <button
                                type="button"
                                className="text-corridor-muted hover:text-white p-1"
                                aria-expanded={isOpen}
                                aria-label={isOpen ? 'Collapse details' : 'Expand details'}
                                onClick={() => setExpanded(isOpen ? null : check.id)}
                              >
                                <span className="material-symbols-outlined text-lg">
                                  {isOpen ? 'expand_less' : 'expand_more'}
                                </span>
                              </button>
                            )}
                          </td>
                        </tr>
                        {isOpen && hasDetail && check.detail && (
                          <tr className="border-b border-white/5 bg-[#111111]">
                            <td colSpan={6} className="p-3">
                              <DetailTable detail={check.detail} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ))}
    </div>
  )
}
