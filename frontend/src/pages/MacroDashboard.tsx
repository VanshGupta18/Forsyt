// Route: "/macroeconomics" (Indian Market Stress Monitor). Combines the
// news-risk score with NIFTY market volatility into a single "today's
// verdict", plus a joint-stress gauge, per-signal metric tables, driving
// headlines, a dual-signal chart, and a stress quadrant map. See
// lib/macroCopy.ts for the logic behind the labels/colors shown here.
import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ApiErrorBanner from '../components/ApiErrorBanner'
import DrivingHeadlines from '../components/DrivingHeadlines'
import DualSignalChart from '../components/DualSignalChart'
import HistoricalAnalogPanel from '../components/HistoricalAnalogPanel'
import JointStressPanel from '../components/JointStressPanel'
import MacroMetricTable from '../components/MacroMetricTable'
import MacroPulseStrip from '../components/MacroPulseStrip'
import StressPositionMap from '../components/StressPositionMap'
import TodayVerdict from '../components/TodayVerdict'
import TopCorridorCard from '../components/TopCorridorCard'
import {
  corridorOperationalRisk,
  fetchDualSignal,
  fetchPageMacro,
  formatPrice,
  orderMarketQuotes,
} from '../lib/api'
import {
  geoRegimeClass,
  geoRegimeLabel,
  MACRO_EYEBROW,
  MACRO_PAGE_DISCLAIMER,
  MACRO_PAGE_SUBTITLE,
  MACRO_PAGE_TITLE,
  macroStatusLine,
  SCORE_LABELS,
  formatGeoChange7d,
  todayVerdict,
  volRegimeClass,
  volRegimeLabel,
  volUnavailableBanner,
} from '../lib/macroCopy'
import { queryKeys } from '../lib/queryClient'

const MACRO_POLL_MS = 15 * 60 * 1000
const CORRIDOR_ELEVATED_RISK = 50

export default function MacroDashboard() {
  const queryClient = useQueryClient()
  const [refreshing, setRefreshing] = useState(false)

  const { data, error, isLoading, isFetching } = useQuery({
    queryKey: queryKeys.macro,
    queryFn: fetchPageMacro,
    refetchInterval: MACRO_POLL_MS,
  })

  const refreshAll = async () => {
    setRefreshing(true)
    try {
      await fetchDualSignal(true)
      await queryClient.invalidateQueries({ queryKey: queryKeys.macro })
    } finally {
      setTimeout(() => setRefreshing(false), 800)
    }
  }

  const dual = data?.dual_signal ?? null
  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility
  const joint = dual?.joint_stress
  const volUnavailable = vol?.available === false
  const gprDisplay = geo?.gpr_index ?? data?.gpr_current?.gpr_index ?? null
  const quotes = orderMarketQuotes(data?.quotes?.quotes ?? [])
  const nifty = quotes.find((q) => q.key === 'nifty')
  const topCorridor = geo?.top_corridor
  const indicators = data?.indicators
  const pipelineRunAt = data?.status?.last_pipeline_runs?.platform_refresh?.run_at ?? null

  const topCorridorRisk = useMemo(() => {
    const topId = topCorridor?.toLowerCase()
    if (!topId) return null
    const row = (data?.corridors?.corridors ?? []).find((c) => c.corridor?.toLowerCase() === topId)
    return row ? corridorOperationalRisk(row) : null
  }, [data?.corridors?.corridors, topCorridor])

  const verdict = todayVerdict(
    joint?.geo_percentile ?? geo?.geo_percentile,
    joint?.vol_percentile ?? vol?.vol_percentile,
    volUnavailable,
    joint?.stress_regime,
  )
  const showVolBanner = volUnavailable && verdict.tone !== 'alert'
  const showAnalog = (dual?.historical_analog?.sample_days ?? 0) >= 3
  const showCorridorCard = Boolean(topCorridor && (topCorridorRisk ?? 0) >= CORRIDOR_ELEVATED_RISK)

  const return7d =
    indicators?.return_7d_pct != null
      ? `${indicators.return_7d_pct > 0 ? '+' : ''}${indicators.return_7d_pct}%`
      : vol?.return_7d_pct != null
        ? `${vol.return_7d_pct > 0 ? '+' : ''}${vol.return_7d_pct}%`
        : '—'

  const trailingVol =
    vol?.trailing_vol_22d != null
      ? `${vol.trailing_vol_22d}%`
      : indicators?.trailing_vol_22d != null
        ? `${indicators.trailing_vol_22d}%`
        : '—'

  const contextGridClass = useMemo(
    () => (showAnalog ? 'grid grid-cols-1 lg:grid-cols-2 gap-4' : ''),
    [showAnalog],
  )

  const quotesLoading = (isLoading || isFetching) && !quotes.length
  const dualLoading = isLoading && !dual
  const quotesError = data?.quotes?.errors?.length ? data.quotes.errors.join(' · ') : null

  return (
    <div className="macro-page corridor-page max-w-container-max mx-auto px-margin-page space-y-4 pb-10">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
        <div className="space-y-2 max-w-2xl">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            {MACRO_EYEBROW}
          </span>
          <h1 className="corridor-display font-headline-lg text-headline-lg">{MACRO_PAGE_TITLE}</h1>
          <p className="font-body-lg text-body-lg text-corridor-muted">{MACRO_PAGE_SUBTITLE}</p>
          {data?.corridors?.index_start && (
            <p className="text-[10px] text-corridor-muted">
              India news index from {data.corridors.index_start}
            </p>
          )}
          <p className="text-xs text-corridor-muted/80 max-w-xl">{MACRO_PAGE_DISCLAIMER}</p>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <button
            type="button"
            onClick={() => void refreshAll()}
            disabled={refreshing}
            className="corridor-btn text-xs px-3 py-1.5"
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <span className="font-label-md text-[11px] text-corridor-muted/70">
            {macroStatusLine(geo?.as_of ?? null, pipelineRunAt)}
          </span>
        </div>
      </header>

      <MacroPulseStrip
        quotes={quotes}
        loading={quotesLoading}
        geoChange7d={geo?.change_7d_pct}
        indexDays={geo?.index_days}
        marketHistories={data?.market_histories?.histories}
      />

      <TodayVerdict
        geoPercentile={joint?.geo_percentile ?? geo?.geo_percentile}
        volPercentile={joint?.vol_percentile ?? vol?.vol_percentile}
        volUnavailable={volUnavailable}
        stressRegime={joint?.stress_regime}
        loading={dualLoading}
      />

      {error instanceof Error && (
        <ApiErrorBanner message={`Macro data: ${error.message}`} onRetry={() => void refreshAll()} />
      )}
      {quotesError && (
        <ApiErrorBanner message={`Market quotes partial: ${quotesError}`} onRetry={() => void refreshAll()} />
      )}

      {showVolBanner && (
        <div className="corridor-alert-banner px-4 py-3 text-sm">
          {volUnavailableBanner(vol?.reason ?? joint?.narrative)}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <JointStressPanel dual={dual} volUnavailable={volUnavailable} />
        <MacroMetricTable
          title={SCORE_LABELS.geo}
          kicker="News-driven risk"
          primary={gprDisplay != null ? String(gprDisplay) : '—'}
          primaryLabel="News risk score"
          regime={geoRegimeLabel(geo?.regime)}
          regimeClass={geoRegimeClass(geo?.regime)}
          rows={[
            {
              label: '7d change',
              value: formatGeoChange7d(geo?.change_7d_pct, geo?.index_days),
            },
            {
              label: '7-day avg score',
              value: geo?.gpr_7ma != null ? String(geo.gpr_7ma) : '—',
            },
          ]}
        />
        <MacroMetricTable
          title={SCORE_LABELS.vol}
          kicker="NIFTY volatility"
          spot={{
            label: 'NIFTY 50',
            price: nifty ? formatPrice(nifty.price, nifty.currency) : '—',
            changePct: nifty?.change_pct,
            loading: quotesLoading,
          }}
          primary={volUnavailable ? 'N/A' : vol?.vol_forecast_5d != null ? `${vol.vol_forecast_5d}%` : '—'}
          primaryLabel="5-day vol forecast"
          regime={volRegimeLabel(volUnavailable ? 'UNAVAILABLE' : vol?.regime)}
          regimeClass={volRegimeClass(volUnavailable ? 'UNAVAILABLE' : vol?.regime)}
          rows={[
            { label: '7d return', value: return7d },
            { label: '22d trailing vol', value: trailingVol },
          ]}
        />
      </div>

      <DrivingHeadlines events={geo?.driving_events} loading={dualLoading} meta={dual?.driving_events_meta} />

      <DualSignalChart
        indexDays={geo?.index_days}
        gprHistory={data?.gpr_history?.history}
        niftyHistory={data?.market_histories?.histories?.nifty}
      />

      <div className={contextGridClass}>
        <StressPositionMap
          geoPercentile={joint?.geo_percentile ?? geo?.geo_percentile}
          volPercentile={joint?.vol_percentile ?? vol?.vol_percentile}
          volUnavailable={volUnavailable}
        />
        {showAnalog && <HistoricalAnalogPanel analog={dual?.historical_analog} />}
      </div>

      {showCorridorCard && <TopCorridorCard corridorId={topCorridor} />}
    </div>
  )
}
