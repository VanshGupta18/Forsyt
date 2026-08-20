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
