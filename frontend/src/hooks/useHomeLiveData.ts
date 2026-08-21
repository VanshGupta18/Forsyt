// ---------------------------------------------------------------------------
// A "custom hook" is just a regular function whose name starts with `use`
// and that's allowed to call other React hooks inside it (here, useQuery).
// It exists to pull reusable logic OUT of a component: instead of Hero.tsx /
// HeroVerdictBlock.tsx duplicating "fetch the home bundle, then figure out
// loading state and the top corridor", they just call `useHomeLiveData()`
// and get a ready-to-render `HomeLiveData` object back. This hook fetches
// GET /api/pages/home (via fetchPageHome in lib/api.ts) with react-query,
// re-fetching automatically every 15 minutes, and reshapes the raw response
// into the friendlier fields the home-page components actually want (a
// single `topCorridor` object instead of having every consumer re-scan the
// corridors array themselves, for example).
// ---------------------------------------------------------------------------
import { useQuery } from '@tanstack/react-query'
import {
  corridorOperationalRisk,
  fetchPageHome,
  formatCorridorName,
  orderMarketQuotes,
  type CorridorRow,
  type CorridorsPayload,
  type DualSignalPayload,
  type MarketQuote,
} from '../lib/api'
import { queryKeys } from '../lib/queryClient'

const INTEL_POLL_MS = 15 * 60 * 1000

export type TopCorridor = { id: string; label: string; risk: number }

export type HomeLiveData = {
  loading: boolean
  quotesLoading: boolean
  error: string | null
  retry: () => void
  quotes: MarketQuote[]
  gprIndex: number | null
  gprDate: string | null
  articles: number | null
  topCorridor: TopCorridor | null
  pipelineRunAt: string | null
  indexStart: string | null
  dual: DualSignalPayload | null
  corridors: CorridorRow[]
  corridorMetadata: CorridorsPayload['metadata']
}

// Scans every corridor row and keeps whichever one has the highest
// operational risk score — that becomes the "top corridor" chip/link shown
// on the home hero. A simple linear max-search; returns null if there are no
// corridors with a `corridor` id yet (e.g. before the first API response lands).
function pickTopCorridor(rows: CorridorRow[]): TopCorridor | null {
  let best: CorridorRow | null = null
  let bestRisk = -Infinity
  for (const row of rows) {
    const risk = corridorOperationalRisk(row)
    if (risk > bestRisk && row.corridor) {
      bestRisk = risk
      best = row
    }
  }
  if (!best?.corridor) return null
  return {
    id: best.corridor.toLowerCase(),
    label: formatCorridorName(best.corridor, best.corridor_name),
    risk: bestRisk,
  }
}

export function useHomeLiveData(): HomeLiveData {
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: queryKeys.home,
    queryFn: fetchPageHome,
    refetchInterval: INTEL_POLL_MS,
  })

  const quotes = orderMarketQuotes(data?.quotes?.quotes ?? [])

  return {
    loading: isLoading && !data,
    quotesLoading: isFetching && !quotes.length,
    error: error instanceof Error ? error.message : null,
    retry: () => {
      void refetch()
    },
    quotes,
    gprIndex: data?.gpr_current?.gpr_index ?? null,
    gprDate: data?.gpr_current?.date ?? null,
    articles: data?.health?.total_articles ?? null,
    topCorridor: pickTopCorridor(data?.corridors?.corridors ?? []),
    pipelineRunAt: data?.status?.last_pipeline_runs?.platform_refresh?.run_at ?? null,
    indexStart:
      data?.corridors?.index_start ?? data?.dual_signal?.index_start ?? null,
    dual: data?.dual_signal ?? null,
    corridors: data?.corridors?.corridors ?? [],
    corridorMetadata: data?.corridors?.metadata,
  }
}
