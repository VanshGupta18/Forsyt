// Macro page section showing the headlines the backend judged as actually
// driving today's news-risk score, in a CorridorNewsTicker strip.
import { Link } from 'react-router-dom'
import CorridorNewsTicker from './CorridorNewsTicker'
import { macroNewsEmptyLine } from '../lib/macroCopy'
import type { DualSignalPayload, NewsArticle } from '../lib/api'

type Props = {
  events?: NewsArticle[]
  loading?: boolean
  meta?: DualSignalPayload['driving_events_meta']
}

export default function DrivingHeadlines({ events, loading, meta }: Props) {
  const articles = (events ?? []).slice(0, 8)

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div>
          <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold">
            Headlines driving today&apos;s news risk
          </h2>
          {meta?.gate_b_relaxed && (
            <p className="text-[10px] text-corridor-watch mt-0.5">Geo stress headlines — limited market overlap today</p>
          )}
        </div>
        <Link to="/news" className="text-xs text-corridor-muted underline hover:text-white shrink-0">
          View all news
        </Link>
      </div>
      <CorridorNewsTicker
        articles={articles}
        loading={loading}
        emptyMessage={macroNewsEmptyLine()}
      />
    </section>
  )
}
