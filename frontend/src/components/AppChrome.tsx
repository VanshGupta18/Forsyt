import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, useLocation } from 'react-router-dom'
import ForsytLogo from './ForsytLogo'
import { fetchHealth, fetchPageHome, formatPrice, orderMarketQuotes, type MarketQuote } from '../lib/api'
import { changeClass } from '../lib/macroCopy'
import { MAIN_NAV } from '../lib/modules'
import { queryKeys } from '../lib/queryClient'

const HEALTH_POLL_MS = 30_000
const HOME_POLL_MS = 5 * 60 * 1000

function TickerStrip({ quotes, loading }: { quotes: MarketQuote[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex items-center gap-6 pr-6 shrink-0">
        {['nifty', 'sensex', 'india_vix'].map((key) => (
          <span key={key} className="font-label-md whitespace-nowrap text-corridor-muted">
            Loading…
          </span>
        ))}
      </div>
    )
  }

  if (!quotes.length) {
    return (
      <div className="flex items-center pr-6 shrink-0">
        <Link to="/macroeconomics" className="font-label-md whitespace-nowrap text-corridor-muted hover:text-white">
          Market data unavailable
        </Link>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-6 pr-6 shrink-0">
      {quotes.map((q, i) => (
        <Link
          key={`${q.key}-${i}`}
          to="/macroeconomics"
          className="font-label-md whitespace-nowrap flex items-center gap-3 hover:opacity-80 transition-opacity"
        >
          <span className="text-corridor-muted">{q.label}</span>
          <span className="text-white tabular-nums">{formatPrice(q.price, q.currency)}</span>
          <span className={`tabular-nums ${changeClass(q.change_pct)}`}>
            {q.change_pct >= 0 ? '+' : ''}
            {q.change_pct}%
          </span>
          <span className="text-white/20">/////</span>
        </Link>
      ))}
    </div>
  )
}

function ChromeTicker({ quotes, loading }: { quotes: MarketQuote[]; loading: boolean }) {
  return (
    <div className="app-chrome-ticker border-t border-[var(--chrome-border)] overflow-hidden py-2">
      <div className="app-chrome-ticker-track flex w-max animate-marquee hover:[animation-play-state:paused]">
        <TickerStrip quotes={quotes} loading={loading} />
        <TickerStrip quotes={quotes} loading={loading} />
      </div>
    </div>
  )
}

export default function AppChrome() {
  const { pathname } = useLocation()
  const isHome = pathname === '/'
  const [mobileOpen, setMobileOpen] = useState(false)

  const { data: health } = useQuery({
    queryKey: queryKeys.health,
    queryFn: fetchHealth,
    refetchInterval: HEALTH_POLL_MS,
  })

  const { data: homeData, isFetching: homeFetching } = useQuery({
    queryKey: queryKeys.home,
    queryFn: fetchPageHome,
    enabled: isHome,
    refetchInterval: HOME_POLL_MS,
  })

  useEffect(() => {
    document.body.dataset.homeChrome = isHome ? 'true' : 'false'
    return () => {
      delete document.body.dataset.homeChrome
    }
  }, [isHome])

  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

  const healthy = health ? health.status === 'healthy' : null
  const quotes = orderMarketQuotes(homeData?.quotes?.quotes ?? [])
  const quotesLoading = isHome && homeFetching && !quotes.length

  const statusDotClass =
    healthy === false ? 'bg-corridor-alert' : healthy ? 'bg-corridor-clear' : 'bg-corridor-muted'

  return (
    <header
      className="app-header corridor-page fixed top-0 left-0 right-0 z-50 bg-[var(--chrome-bg)] border-b border-[var(--chrome-border)]"
      data-home={isHome ? 'true' : undefined}
    >
      <div className="flex items-center h-12 px-margin-page max-w-container-max mx-auto gap-4">
        <Link to="/" className="shrink-0 hover:opacity-80 transition-opacity">
          <ForsytLogo />
        </Link>

        <nav className="hidden lg:flex items-center gap-0.5">
          {MAIN_NAV.map((link) => (
            <NavLink key={link.to} to={link.to} className="corridor-tab px-3 py-2 text-[10px]">
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <span className="hidden sm:flex items-center gap-1.5" title={healthy === false ? 'Degraded' : healthy ? 'Live' : 'Checking'}>
            <span className={`w-1.5 h-1.5 shrink-0 ${statusDotClass}`} />
            <span className="corridor-kicker normal-case text-[10px] tracking-normal">
              {healthy === null ? '…' : healthy ? 'Live' : 'Degraded'}
            </span>
          </span>
          <span className={`sm:hidden w-1.5 h-1.5 shrink-0 ${statusDotClass}`} aria-label={healthy ? 'Live' : 'Degraded'} />

          <button
            type="button"
            className="lg:hidden corridor-btn p-1.5 text-white"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((o) => !o)}
          >
            <span className="material-symbols-outlined text-[22px]">{mobileOpen ? 'close' : 'menu'}</span>
          </button>
        </div>
      </div>

      {isHome && <ChromeTicker quotes={quotes} loading={quotesLoading} />}

      {mobileOpen && (
        <nav className="lg:hidden border-t border-[var(--chrome-border)] bg-[var(--chrome-bg)] px-margin-page py-2 flex flex-col gap-0.5">
          {MAIN_NAV.map((link) => (
            <NavLink key={link.to} to={link.to} className="corridor-tab px-2 py-2.5 text-[11px] w-fit">
              {link.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
