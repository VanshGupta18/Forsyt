import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ApiErrorBanner from '../components/ApiErrorBanner'
import CorridorNewsTicker from '../components/CorridorNewsTicker'
import DrivingHeadlines from '../components/DrivingHeadlines'
import DualSignalChart from '../components/DualSignalChart'
import HistoricalAnalogPanel from '../components/HistoricalAnalogPanel'
import JointStressPanel from '../components/JointStressPanel'
import MacroMetricTable from '../components/MacroMetricTable'
import MacroNextSteps from '../components/MacroNextSteps'
import MacroPulseStrip from '../components/MacroPulseStrip'
import StressPositionMap from '../components/StressPositionMap'
import TodayVerdict from '../components/TodayVerdict'
import TopCorridorCard from '../components/TopCorridorCard'
import TransmissionStrip from '../components/TransmissionStrip'
import {
  fetchDualSignal,
  fetchGprCurrent,
  fetchMarketIndicators,
  fetchMarketQuotes,
  fetchPlatformStatus,
  formatCorridorName,
  formatPrice,
  orderMarketQuotes,
  type DualSignalPayload,
  type MarketQuote,
  type NewsArticle,
} from '../lib/api'
import {
  geoRegimeClass,
  geoRegimeLabel,
  highStressBanner,
  MACRO_EYEBROW,
  MACRO_HEADLINES_TITLE,
  MACRO_PAGE_DISCLAIMER,
  MACRO_PAGE_SUBTITLE,
  MACRO_PAGE_TITLE,
  macroStatusLine,
  macroNewsEmptyLine,
  SCORE_LABELS,
  volRegimeClass,
  volRegimeLabel,
  volUnavailableBanner,
} from '../lib/macroCopy'
import { fetchMacroMarketNews, mergeMacroHeadlines } from '../lib/macroNews'

const MACRO_NEWS_POLL_MS = 15 * 60 * 1000
const MACRO_POLL_MS = 15 * 60 * 1000

export default function MacroDashboard() {
  const [dual, setDual] = useState<DualSignalPayload | null>(null)
  const [gprCurrent, setGprCurrent] = useState<number | null>(null)
  const [quotes, setQuotes] = useState<MarketQuote[]>([])
  const [indicators, setIndicators] = useState<{ trailing_vol_22d?: number | null; return_7d_pct?: number | null } | null>(null)
  const [headlines, setHeadlines] = useState<NewsArticle[]>([])
  const [headlinesLoading, setHeadlinesLoading] = useState(false)
  const [dualError, setDualError] = useState<string | null>(null)
  const [quotesError, setQuotesError] = useState<string | null>(null)
  const [quotesLoading, setQuotesLoading] = useState(true)
  const [dualLoading, setDualLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pipelineRunAt, setPipelineRunAt] = useState<string | null>(null)

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

  const loadHeadlines = useCallback(async (driving?: NewsArticle[]) => {
    setHeadlinesLoading(true)
    try {
      const feed = await fetchMacroMarketNews(8)
      setHeadlines(mergeMacroHeadlines(driving, feed, 8))
    } catch {
      setHeadlines(mergeMacroHeadlines(driving, [], 8))
    } finally {
      setHeadlinesLoading(false)
    }
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
    loadHeadlines(dual?.geopolitical?.driving_events)
  }, [dual?.geopolitical?.driving_events, loadHeadlines])

  useEffect(() => {
    const id = window.setInterval(() => {
      loadHeadlines(dual?.geopolitical?.driving_events)
    }, MACRO_NEWS_POLL_MS)
    return () => window.clearInterval(id)
  }, [dual?.geopolitical?.driving_events, loadHeadlines])

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
  const showHighStressBanner = (joint?.stress_regime ?? '').toUpperCase() === 'HIGH_STRESS'
  const showVolBanner = volUnavailable

  const topCorridor = geo?.top_corridor
  const topCorridorLabel = topCorridor ? formatCorridorName(topCorridor) : '—'
  const topCorridorHref = topCorridor
    ? `/trade-corridor?corridor=${encodeURIComponent(topCorridor.toLowerCase())}`
    : '/trade-corridor'

  const return7d =
    indicators?.return_7d_pct != null
      ? `${indicators.return_7d_pct > 0 ? '+' : ''}${indicators.return_7d_pct}%`
      : vol?.return_7d_pct != null
        ? `${vol.return_7d_pct > 0 ? '+' : ''}${vol.return_7d_pct}%`
        : '—'

  return (
    <div className="macro-page corridor-page max-w-container-max mx-auto px-margin-page space-y-4 pb-12">
      <header className="flex flex-wrap items-start justify-between gap-4 pt-2">
        <div className="space-y-2 max-w-2xl">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            {MACRO_EYEBROW}
          </span>
          <h1 className="corridor-display font-headline-lg text-headline-lg">{MACRO_PAGE_TITLE}</h1>
          <p className="text-sm text-corridor-muted">{MACRO_PAGE_SUBTITLE}</p>
          <p className="text-[11px] text-corridor-muted/70">
            {macroStatusLine(geo?.as_of ?? null, pipelineRunAt)}
          </p>
        </div>
        <button
          type="button"
          onClick={refreshAll}
          disabled={refreshing}
          className="corridor-btn px-4 py-2 text-sm shrink-0"
        >
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      <MacroPulseStrip quotes={quotes} loading={quotesLoading} />

      <TodayVerdict
        geoPercentile={joint?.geo_percentile ?? geo?.geo_percentile}
        volPercentile={joint?.vol_percentile ?? vol?.vol_percentile}
        volUnavailable={volUnavailable}
        stressRegime={joint?.stress_regime}
        loading={dualLoading && !dual}
      />

      {dualError && <ApiErrorBanner message={`Dual-signal: ${dualError}`} onRetry={() => loadDual(true)} />}
      {quotesError && <ApiErrorBanner message={`Market quotes partial: ${quotesError}`} onRetry={loadQuotes} />}

      {showHighStressBanner && (
        <div className="corridor-alert-banner px-4 py-3 text-sm">{highStressBanner()}</div>
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
              value:
                geo?.change_7d_pct != null
                  ? `${geo.change_7d_pct > 0 ? '+' : ''}${geo.change_7d_pct}%`
                  : '—',
            },
            {
              label: 'Top corridor',
              value: topCorridorLabel,
              href: topCorridor ? topCorridorHref : undefined,
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
          rows={[{ label: '7d return', value: return7d }]}
        />
      </div>

      <StressPositionMap
        geoPercentile={joint?.geo_percentile ?? geo?.geo_percentile}
        volPercentile={joint?.vol_percentile ?? vol?.vol_percentile}
        volUnavailable={volUnavailable}
      />

      <DrivingHeadlines events={geo?.driving_events} loading={dualLoading && !dual} />

      <HistoricalAnalogPanel analog={dual?.historical_analog} />

      <TransmissionStrip quotes={quotes} geoChange7d={geo?.change_7d_pct} loading={quotesLoading} />

      <TopCorridorCard corridorId={topCorridor} />

      <DualSignalChart />

      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold">
            {MACRO_HEADLINES_TITLE}
          </h2>
          <Link to="/news" className="text-xs text-corridor-muted underline hover:text-white">
            View all news
          </Link>
        </div>
        <CorridorNewsTicker
          articles={headlines}
          loading={headlinesLoading}
          emptyMessage={macroNewsEmptyLine()}
        />
      </section>

      <MacroNextSteps
        geoPercentile={joint?.geo_percentile ?? geo?.geo_percentile}
        volPercentile={joint?.vol_percentile ?? vol?.vol_percentile}
        volUnavailable={volUnavailable}
        topCorridor={topCorridor}
      />

      <p className="text-[10px] text-corridor-muted text-center pt-2">{MACRO_PAGE_DISCLAIMER}</p>
    </div>
  )
}
