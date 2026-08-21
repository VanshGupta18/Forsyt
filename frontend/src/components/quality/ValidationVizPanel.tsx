// Quality page's "technical details" visuals: a color-coded heatmap grid of
// every check's status, plus a short list of key checks shown as progress
// bars. `barWidth()` below picks a sensible bar length per check since
// checks report wildly different kinds of numbers (a 0-1 correlation, a
// percentage, a pass/fail with no number at all).
import { useMemo } from 'react'
import type { QualityCheck, QualityCheckStatus } from '../../lib/api'

const STATUS_CELL: Record<QualityCheckStatus, string> = {
  pass: '#00c853',
  fail: '#ff3333',
  warn: '#f5b800',
  na: '#333333',
}

const STATUS_BAR: Record<QualityCheckStatus, string> = {
  pass: 'bg-corridor-clear',
  fail: 'bg-corridor-alert',
  warn: 'bg-corridor-watch',
  na: 'bg-white/20',
}

type Props = {
  checks: QualityCheck[]
  summary: { checks_passing: number; checks_total: number }
}

function parseNumeric(value: string | number | null): number | null {
  if (value == null) return null
  if (typeof value === 'number') return value
  const n = parseFloat(String(value).replace(/[^0-9.-]/g, ''))
  return Number.isFinite(n) ? n : null
}

function barWidth(check: QualityCheck): number {
  const n = parseNumeric(check.value)
  if (n == null) return check.status === 'pass' ? 85 : check.status === 'fail' ? 25 : 40
  if (check.id.includes('caldara') || check.title.toLowerCase().includes('correlation')) {
    return Math.min(100, Math.max(0, n * 100))
  }
  if (check.id.includes('coverage') || check.title.toLowerCase().includes('coverage')) {
    return Math.min(100, n)
  }
  if (check.id.includes('leakage')) {
    return check.status === 'pass' ? 92 : 35
  }
  if (n >= 0 && n <= 1) return n * 100
  if (n >= 0 && n <= 100) return n
  return check.status === 'pass' ? 80 : 30
}

export default function ValidationVizPanel({ checks, summary }: Props) {
  const cells = useMemo(() => {
    const ordered = [...checks].sort((a, b) => {
      const order: Record<string, number> = { pass: 0, warn: 1, fail: 2, na: 3 }
      return (order[a.status] ?? 4) - (order[b.status] ?? 4)
    })
    return ordered.slice(0, 80)
  }, [checks])

  const topBars = useMemo(() => {
    const matchers = [
      (c: QualityCheck) => c.id === 'gpr_caldara_ma30',
      (c: QualityCheck) => c.id === 'corridor_parent_leakage',
      (c: QualityCheck) => c.id === 'pipeline_nlp_coverage',
      (c: QualityCheck) => c.title.toLowerCase().includes('event spike'),
      (c: QualityCheck) => c.id === 'market_vol_gpr_incremental',
    ]
    const picks: QualityCheck[] = []
    for (const match of matchers) {
      const found = checks.find(match)
      if (found && !picks.includes(found)) picks.push(found)
    }
    if (picks.length < 4) {
      for (const c of checks) {
        if (picks.length >= 5) break
        if (!picks.includes(c) && c.status !== 'na') picks.push(c)
      }
    }
    return picks.slice(0, 5)
  }, [checks])

  const passPct =
    summary.checks_total > 0 ? Math.round((summary.checks_passing / summary.checks_total) * 100) : 0

  return (
    <div className="corridor-panel p-5 space-y-5 quality-viz-panel">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Validation heatmap grid — NERAI-style */}
        <div className="space-y-3">
          <span className="corridor-kicker">Validation heatmap</span>
          <div
            className="grid gap-[3px]"
            style={{ gridTemplateColumns: 'repeat(10, minmax(0, 1fr))' }}
            role="img"
            aria-label={`Validation status grid: ${summary.checks_passing} of ${summary.checks_total} checks passing`}
          >
            {cells.map((check, i) => (
              <div
                key={check.id}
                title={`${check.title}: ${check.status}`}
                className="quality-heatmap-cell aspect-square rounded-sm transition-transform hover:scale-110"
                style={{
                  backgroundColor: STATUS_CELL[check.status],
                  opacity: check.status === 'na' ? 0.35 : 0.85,
                  animationDelay: `${i * 15}ms`,
                }}
              />
            ))}
            {cells.length < 80 &&
              Array.from({ length: 80 - cells.length }).map((_, i) => (
                <div
                  key={`pad-${i}`}
                  className="aspect-square rounded-sm bg-white/[0.04]"
                />
              ))}
          </div>
          <div className="flex flex-wrap gap-3 text-[10px] text-corridor-muted uppercase tracking-wider">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-corridor-clear" /> Pass
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-corridor-watch" /> Warn
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-corridor-alert" /> Fail
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-white/20" /> N/A
            </span>
          </div>
        </div>

        {/* Top validation indices — NERAI-style bars */}
        <div className="space-y-3">
          <span className="corridor-kicker">Key validation indices</span>
          <ul className="space-y-3">
            {topBars.map((check) => {
              const width = barWidth(check)
              return (
                <li key={check.id} className="space-y-1">
                  <div className="flex justify-between items-baseline gap-2">
                    <span className="text-xs text-white truncate">{check.title}</span>
                    <span className="corridor-score text-sm text-white shrink-0">{check.value ?? '—'}</span>
                  </div>
                  <div className="h-1.5 bg-white/10 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-700 ${STATUS_BAR[check.status]}`}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
          <div className="pt-2 border-t border-white/5 flex justify-between items-center">
            <span className="corridor-kicker">Overall pass rate</span>
            <span className="corridor-score text-2xl text-white">{passPct}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
