// News page panel showing the current GPR score (latest/7d/30d averages)
// plus a compact embedded GprHistoryChart and links to the other dashboards.
import { Link } from 'react-router-dom'
import { NEWS_RISK_CONTEXT_TITLE } from '../lib/newsCopy'
import type { GprHistoryPoint } from '../lib/api'
import GprHistoryChart from './GprHistoryChart'

type Props = {
  gprIndex: number | null
  gprDate: string | null
  gpr7ma: number | null
  gpr30ma: number | null
  gprHistory?: GprHistoryPoint[]
}

function formatScore(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return value.toFixed(2)
}

export default function NewsRiskPanel({ gprIndex, gprDate, gpr7ma, gpr30ma, gprHistory = [] }: Props) {
  return (
    <section className="corridor-panel p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3 shrink-0">
        <h2 className="corridor-kicker">{NEWS_RISK_CONTEXT_TITLE}</h2>
        {gprDate && (
          <p className="text-[10px] text-corridor-muted">News risk data through {gprDate.slice(0, 10)}</p>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 shrink-0 max-w-md">
        <div className="news-risk-stat">
          <p className="corridor-kicker">Latest</p>
          <span className="corridor-score text-xl text-corridor-watch">{formatScore(gprIndex)}</span>
        </div>
        <div className="news-risk-stat">
          <p className="corridor-kicker">7-day avg</p>
          <span className="corridor-score text-lg text-white">{formatScore(gpr7ma)}</span>
        </div>
        <div className="news-risk-stat">
          <p className="corridor-kicker">30-day avg</p>
          <span className="corridor-score text-lg text-corridor-muted">{formatScore(gpr30ma)}</span>
        </div>
      </div>

      <div className="h-[240px] shrink-0">
        <GprHistoryChart height={240} variant="corridor" period="3mo" compact className="h-full" history={gprHistory} />
      </div>

      <div className="flex flex-wrap gap-3 text-xs shrink-0">
        <Link to="/macroeconomics" className="text-corridor-muted underline hover:text-white">
          Market stress monitor →
        </Link>
        <Link to="/trade-corridor" className="text-corridor-muted underline hover:text-white">
          Trade route risk →
        </Link>
      </div>
    </section>
  )
}
