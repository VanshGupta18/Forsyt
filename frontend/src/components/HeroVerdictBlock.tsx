import { Link } from 'react-router-dom'
import PulseCard from './PulseCard'
import type { HomeLiveData } from '../hooks/useHomeLiveData'
import { HOME_EYEBROW, HOME_TITLE } from '../lib/homeCopy'
import {
  changeClass,
  geoRegimeClass,
  geoRegimeLabel,
  stressQuadrantId,
  titleAccent,
  todayVerdict,
  type StressQuadrantId,
} from '../lib/macroCopy'

const CORRIDOR_ELEVATED_RISK = 50

type Destination = { to: string; label: string }

const DESTINATIONS: Destination[] = [
  { to: '/news', label: 'Headlines' },
  { to: '/macroeconomics', label: 'Market stress' },
  { to: '/trade-corridor', label: 'Corridor risk' },
]

function quadrantChipLabel(q: StressQuadrantId): string {
  if (q === 'calm') return 'Calm'
  if (q === 'geo') return 'Headline-led'
  if (q === 'vol') return 'Market-led'
  return 'Aligned stress'
}

function pickPrimary(
  topCorridor: HomeLiveData['topCorridor'],
  geoPercentile?: number | null,
  volPercentile?: number | null,
  volUnavailable?: boolean,
): Destination {
  if (topCorridor && topCorridor.risk >= CORRIDOR_ELEVATED_RISK) {
    return {
      to: `/trade-corridor?corridor=${encodeURIComponent(topCorridor.id)}`,
      label: 'Corridor risk',
    }
  }
  const q = stressQuadrantId(geoPercentile, volPercentile, volUnavailable)
  if (q === 'vol') return DESTINATIONS[1]
  return DESTINATIONS[0]
}

type Props = {
  live: HomeLiveData
}

export default function HeroVerdictBlock({ live }: Props) {
  const { loading, quotesLoading, gprIndex, topCorridor, quotes, dual } = live

  const geo = dual?.geopolitical
  const vol = dual?.nifty_volatility
  const volUnavailable = vol?.available === false

  const verdictReady = !loading && dual != null
  const verdict = verdictReady
    ? todayVerdict(geo?.geo_percentile, vol?.vol_percentile, volUnavailable, dual.joint_stress?.stress_regime)
    : null

  const quadrant = stressQuadrantId(geo?.geo_percentile, vol?.vol_percentile, volUnavailable)
  const regime = geo?.regime ?? ''
  const regimeLabel = geoRegimeLabel(regime)
  const regimeClass = geoRegimeClass(regime)
  const indexStart = live.indexStart
  const calibratingIndex =
    (geo?.index_days != null && geo.index_days < 8) ||
    geo?.geo_percentile_confidence === 'low'

  const corridorHref = topCorridor
    ? `/trade-corridor?corridor=${encodeURIComponent(topCorridor.id)}`
    : '/trade-corridor'

  const nifty = quotes.find((q) => q.key === 'nifty')
  const niftyValue =
    quotesLoading || loading
      ? '…'
      : nifty
        ? `${nifty.change_pct >= 0 ? '+' : ''}${nifty.change_pct}%`
        : '—'
  const niftyClass = nifty ? changeClass(nifty.change_pct) : 'text-corridor-muted'

  const primary = pickPrimary(topCorridor, geo?.geo_percentile, vol?.vol_percentile, volUnavailable)
  const secondary = DESTINATIONS.filter((d) => d.label !== primary.label)

  return (
    <div className="order-2 lg:order-1 min-w-0 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow-badge">
          <span className="eyebrow-dot" />
          {HOME_EYEBROW}
        </span>
        {verdictReady && (
          <span className="text-[10px] uppercase font-semibold tracking-wide px-2 py-0.5 border border-white/15 text-corridor-muted">
            {quadrantChipLabel(quadrant)}
          </span>
        )}
        {calibratingIndex && (
          <span className="text-[10px] uppercase font-semibold tracking-wide px-2 py-0.5 border border-corridor-watch/40 text-corridor-watch">
            Calibrating
          </span>
        )}
      </div>

      {indexStart && (
        <p className="text-[10px] text-corridor-muted">India news index from {indexStart}</p>
      )}

      <div className="space-y-2">
        <h1
          className={`corridor-display font-headline-lg text-headline-lg leading-tight ${
            verdict ? titleAccent(verdict.tone, 'text-white') : 'text-white'
          }`}
        >
          {verdict?.title ?? (loading ? 'Loading today\u2019s picture…' : HOME_TITLE)}
        </h1>
        <p className="font-body-lg text-body-lg text-corridor-muted line-clamp-2 max-w-xl">
          {verdict?.body ?? 'Pulling headline risk, market vol, and corridor signals…'}
        </p>
      </div>

      <div className="home-hero-stats home-pulse-track flex gap-2 pb-1 items-start">
        <div className="flex flex-col gap-2 shrink-0">
          <PulseCard
            label="News risk"
            value={loading ? '…' : gprIndex != null ? String(Math.round(gprIndex)) : '—'}
            valueClass="text-corridor-watch"
            href="/news"
          />
          <PulseCard
            label="NIFTY 50"
            value={niftyValue}
            valueClass={niftyClass}
            href="/macroeconomics"
          />
        </div>
        <PulseCard label="Regime" value={loading ? '…' : regimeLabel} valueClass={regimeClass} />
        <PulseCard
          label="Top corridor"
          value={loading ? '…' : topCorridor?.label ?? '—'}
          valueClass="text-corridor-alert"
          href={corridorHref}
          valueSize="lg"
          className="max-w-[180px]"
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
        <Link to={primary.to} className="home-hero-cta">
          {primary.label}
          <span className="material-symbols-outlined text-base">arrow_forward</span>
        </Link>
        {secondary.map(({ to, label }) => (
          <Link key={to} to={to} className="home-hero-cta">
            {label}
            <span className="material-symbols-outlined text-base">arrow_forward</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
