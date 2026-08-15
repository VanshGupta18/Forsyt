import { useCallback, useEffect, useMemo, useState } from 'react'
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
  fetchCorridors,
  fetchDualSignal,
  fetchGprCurrent,
  fetchMarketIndicators,
  fetchMarketQuotes,
  fetchPlatformStatus,
  formatPrice,
  orderMarketQuotes,
  type DualSignalPayload,
  type MarketQuote,
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

const MACRO_POLL_MS = 15 * 60 * 1000
const CORRIDOR_ELEVATED_RISK = 50

export default function MacroDashboard() {
  const [dual, setDual] = useState<DualSignalPayload | null>(null)
  const [gprCurrent, setGprCurrent] = useState<number | null>(null)
  const [quotes, setQuotes] = useState<MarketQuote[]>([])
  const [indicators, setIndicators] = useState<{ trailing_vol_22d?: number | null; return_7d_pct?: number | null } | null>(null)
  const [dualError, setDualError] = useState<string | null>(null)
  const [quotesError, setQuotesError] = useState<string | null>(null)
  const [quotesLoading, setQuotesLoading] = useState(true)
  const [dualLoading, setDualLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pipelineRunAt, setPipelineRunAt] = useState<string | null>(null)
  const [topCorridorRisk, setTopCorridorRisk] = useState<number | null>(null)

  const loadQuotes = useCallback(() => {
    setQuotesLoading(true)
    setQuotesError(null)
    fetchMarketQuotes()
      .then((p) => {
        setQuotes(orderMarketQuotes(p.quotes ?? []))
        if (p.errors?.length) setQuotesError(p.errors.join(' · '))
      })
      .catch((e: Error) => {
        setQuotes([])
        setQuotesError(e.message)
      })
      .finally(() => setQuotesLoading(false))
    fetchMarketIndicators('nifty')
      .then(setIndicators)
      .catch(() => undefined)
  }, [])

  const loadDual = useCallback((refresh = false) => {
    setDualError(null)
    setDualLoading(true)
    fetchDualSignal(refresh)
      .then(setDual)
      .catch((e: Error) => setDualError(e.message))
      .finally(() => setDualLoading(false))
  }, [])

  useEffect(() => {
    loadQuotes()
    loadDual(false)
    fetchGprCurrent()
      .then((g) => setGprCurrent(g.gpr_index ?? null))
      .catch(() => undefined)
  }, [loadDual, loadQuotes])

  useEffect(() => {
    const refreshStatus = () => {
      fetchPlatformStatus()
        .then((status) => {
          setPipelineRunAt(status.last_pipeline_runs?.platform_refresh?.run_at ?? null)
        })
        .catch(() => undefined)
    }
    refreshStatus()
    const id = window.setInterval(refreshStatus, MACRO_POLL_MS)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    const id = window.setInterval(() => {
      loadDual(false)
      fetchGprCurrent()
        .then((g) => setGprCurrent(g.gpr_index ?? null))
        .catch(() => undefined)
    }, MACRO_POLL_MS)
    return () => window.clearInterval(id)
  }, [loadDual])

  useEffect(() => {
    fetchCorridors()
      .then((payload) => {
        const topId = dual?.geopolitical?.top_corridor?.toLowerCase()
        if (!topId) {
          setTopCorridorRisk(null)
          return
        }
        const row = (payload.corridors ?? []).find((c) => c.corridor?.toLowerCase() === topId)
        setTopCorridorRisk(row ? corridorOperationalRisk(row) : null)
      })
      .catch(() => setTopCorridorRisk(null))
  }, [dual?.geopolitical?.top_corridor])

  const refreshAll = () => {
    setRefreshing(true)
    loadQuotes()
    loadDual(true)
    fetchGprCurrent()
      .then((g) => setGprCurrent(g.gpr_index ?? null))
      .catch(() => undefined)
    setTimeout(() => setRefreshing(false), 800)
  }

  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility
  const joint = dual?.joint_stress
  const volUnavailable = vol?.available === false
  const gprDisplay = geo?.gpr_index ?? gprCurrent
  const nifty = quotes.find((q) => q.key === 'nifty')
  const topCorridor = geo?.top_corridor

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
    vol?.trailing_vol_22d != null ? `${vol.trailing_vol_22d}%` : indicators?.trailing_vol_22d != null ? `${indicators.trailing_vol_22d}%` : '—'

  const contextGridClass = useMemo(
    () => (showAnalog ? 'grid grid-cols-1 lg:grid-cols-2 gap-4' : ''),
    [showAnalog],
  )

  return (
    <div className="macro-page corridor-page max-w-container-max mx-auto px-margin-page space-y-4 pb-10">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
        <div className="space-y-2 max-w-2xl">
          <span
            className="eyebrow-badge"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.85)' }}
          >
            <span
              className="eyebrow-dot"
              style={{ background: '#ffffff', boxShadow: '0 0 8px 2px rgba(255,255,255,0.25)' }}
            />
            {MACRO_EYEBROW}
          </span>
          <h1 className="corridor-display font-headline-lg text-headline-lg">{MACRO_PAGE_TITLE}</h1>
          <p className="font-body-lg text-body-lg text-corridor-muted">{MACRO_PAGE_SUBTITLE}</p>
          <p className="text-xs text-corridor-muted/80 max-w-xl">{MACRO_PAGE_DISCLAIMER}</p>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <button
            type="button"
            onClick={refreshAll}
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
      />

      <TodayVerdict
        geoPercentile={joint?.geo_percentile ?? geo?.geo_percentile}
        volPercentile={joint?.vol_percentile ?? vol?.vol_percentile}
        volUnavailable={volUnavailable}
        stressRegime={joint?.stress_regime}
        loading={dualLoading && !dual}
      />

      {dualError && <ApiErrorBanner message={`Dual-signal: ${dualError}`} onRetry={() => loadDual(true)} />}
      {quotesError && <ApiErrorBanner message={`Market quotes partial: ${quotesError}`} onRetry={loadQuotes} />}

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

      <DrivingHeadlines
        events={geo?.driving_events}
        loading={dualLoading && !dual}
        meta={dual?.driving_events_meta}
      />

      <DualSignalChart indexDays={geo?.index_days} />

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
