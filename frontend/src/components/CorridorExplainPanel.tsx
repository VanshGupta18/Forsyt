// "Why is this corridor's risk score where it is today?" — a precomputed AI
// explanation (generated once a day by news_dataset/pipeline/explain_corridors.py,
// not live) shown on the corridor detail panel. Renders nothing if no
// explanation exists yet for this corridor (a fresh corridor, or the daily
// batch job hasn't run yet) rather than showing an error.
import { useQuery } from '@tanstack/react-query'
import { fetchCorridorExplanation } from '../lib/api'

export default function CorridorExplainPanel({ corridorId }: { corridorId: string | null }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['corridor-explanation', corridorId],
    queryFn: () => fetchCorridorExplanation(corridorId as string),
    enabled: Boolean(corridorId),
    retry: false,
    staleTime: 30 * 60 * 1000,
  })

  if (!corridorId || isError) return null

  return (
    <div className="mt-3 p-3 rounded-sm bg-[#0d0d0d]">
      <div className="flex items-center justify-between mb-1.5">
        <strong className="text-sm text-[var(--corridor-text)]">Why this score?</strong>
        <span className="text-[9px] uppercase tracking-wide text-corridor-muted/60">AI-generated · daily</span>
      </div>
      {isLoading ? (
        <p className="text-xs text-corridor-muted">Loading…</p>
      ) : (
        <p className="text-xs text-corridor-muted leading-relaxed">{data?.explanation_text}</p>
      )}
    </div>
  )
}
