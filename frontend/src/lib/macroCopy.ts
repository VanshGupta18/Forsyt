import { businessTierClass, businessTierLabel, formatPipelineRunAt } from './corridorCopy'

export const MACRO_EYEBROW = 'Live market stress monitoring'

export const MACRO_PAGE_TITLE = 'Indian Market Stress Monitor'

export const MACRO_PAGE_SUBTITLE =
  'Your daily check: is stress from headlines, markets, or both — and does it change your investing plan?'

export const MACRO_PAGE_DISCLAIMER =
  'Stress scores reflect recent Indian news and market prices — not trading advice or forecasts.'

export const MACRO_DATA_REFRESH_NOTE = 'geo scores update hourly in cloud'

export function macroStatusLine(
  geoDate: string | null | undefined,
  pipelineRunAt?: string | null,
): string {
  const through = geoDate ? `Geo data through ${geoDate.slice(0, 10)}` : 'Waiting for geo data'
  const base = `${through} · ${MACRO_DATA_REFRESH_NOTE}`
  const run = formatPipelineRunAt(pipelineRunAt)
  return run ? `${base} · recomputed ${run}` : base
}

export const SCORE_LABELS = {
  joint: 'Combined stress',
  geo: 'News-driven risk',
  vol: 'Market volatility',
  geoPct: 'News risk vs history',
  volPct: 'Vol vs history',
} as const

export const MACRO_HEADLINES_TITLE = 'Latest market & stress news'

export function macroNewsEmptyLine(): string {
  return 'No verified stress headlines today — news risk may be driven by older flow.'
}

export function whyIncludedLabel(why?: string): string {
  if (why === 'corridor_match') return 'Route'
  if (why === 'market_keyword') return 'Market'
  if (why === 'geo_theme') return 'Geo'
  return ''
}

export function stressQuadrantShortLabel(
  geoPercentile?: number | null,
  volPercentile?: number | null,
  volUnavailable?: boolean,
): string {
  const q = stressQuadrantId(geoPercentile, volPercentile, volUnavailable)
  if (q === 'calm') return 'Calm quadrant'
  if (q === 'geo') return 'Headline-led · market calm'
  if (q === 'vol') return 'Market-led · headlines moderate'
  return 'Both signals elevated'
}

export function stressRegimeLabel(regime?: string): string {
  const r = (regime ?? '').toUpperCase()
  if (r === 'HIGH_STRESS') return 'High stress'
  if (r === 'WATCH') return 'Watch'
  if (r === 'CALM') return 'Calm'
  if (r === 'UNAVAILABLE') return 'Unavailable'
  return regime ?? '—'
}

export function stressRegimeClass(regime?: string): string {
  const r = (regime ?? '').toUpperCase()
  if (r === 'HIGH_STRESS') return 'text-corridor-alert'
  if (r === 'WATCH') return 'text-corridor-watch'
  if (r === 'CALM') return 'text-corridor-clear'
  return 'text-corridor-muted'
}

export function geoRegimeLabel(regime?: string): string {
  const r = (regime ?? '').toUpperCase()
  if (r === 'LOW') return 'Low concern'
  if (r === 'MODERATE') return 'Moderate'
  if (r === 'ELEVATED') return 'Elevated'
  if (r === 'HIGH') return 'High concern'
  return regime ?? '—'
}

export function geoRegimeClass(regime?: string): string {
  const r = (regime ?? '').toUpperCase()
  if (r === 'HIGH' || r === 'ELEVATED') return 'text-corridor-alert'
  if (r === 'MODERATE') return 'text-corridor-watch'
  if (r === 'LOW') return 'text-corridor-clear'
  return 'text-corridor-muted'
}

export function volRegimeLabel(regime?: string): string {
  const r = (regime ?? '').toUpperCase()
  if (r === 'NORMAL') return 'Normal vol'
  if (r === 'ELEVATED') return 'Elevated vol'
  if (r === 'HIGH_VOL') return 'High volatility'
  if (r === 'UNAVAILABLE') return 'Unavailable'
  return regime ?? '—'
}

export function volRegimeClass(regime?: string): string {
  const r = (regime ?? '').toUpperCase()
  if (r === 'HIGH_VOL' || r === 'ELEVATED') return 'text-corridor-alert'
  if (r === 'NORMAL') return 'text-corridor-clear'
  if (r === 'UNAVAILABLE') return 'text-corridor-muted'
  return 'text-corridor-watch'
}

export function percentileTierClass(value: number): string {
  return businessTierClass(value)
}

export function percentileTierLabel(value: number): string {
  return businessTierLabel(value)
}

export function volUnavailableBanner(reason?: string): string {
  return reason ?? 'Volatility model unavailable — joint stress uses geo signal only.'
}

export function highStressBanner(): string {
  return 'Combined stress is elevated — review exposure and corridor links before committing new risk.'
}

export function stressPositionAdvisory(
  geoPercentile?: number | null,
  volPercentile?: number | null,
  volUnavailable?: boolean,
): string {
  const geoHigh = (geoPercentile ?? 0) >= 50
  const volHigh = volUnavailable ? false : (volPercentile ?? 0) >= 50

  if (!geoHigh && !volHigh) {
    return 'News risk and market vol are both below typical stress — environment is relatively calm.'
  }
  if (geoHigh && !volHigh) {
    return 'Headlines are elevated but markets are still calm — this gap often closes. Avoid pausing SIPs on news alone.'
  }
  if (!geoHigh && volHigh) {
    return 'Markets are pricing stress ahead of headlines — often a correction, not a geopolitical regime shift.'
  }
  return 'Both headlines and market vol are elevated — alignment usually matters more for lump sums than routine SIPs.'
}

export type StressQuadrantId = 'calm' | 'geo' | 'vol' | 'joint'

export function stressQuadrantId(
  geoPercentile?: number | null,
  volPercentile?: number | null,
  volUnavailable?: boolean,
): StressQuadrantId {
  const geoHigh = (geoPercentile ?? 0) >= 50
  const volHigh = volUnavailable ? false : (volPercentile ?? 0) >= 50
  if (geoHigh && volHigh) return 'joint'
  if (geoHigh) return 'geo'
  if (volHigh) return 'vol'
  return 'calm'
}

export const STRESS_MAP_CORNERS = {
  tl: 'Calm',
  tr: 'Headline stress',
  bl: 'Market stress',
  br: 'Both elevated',
} as const

export type TodayVerdictTone = 'clear' | 'watch' | 'alert' | 'muted'

export type TodayVerdictContent = {
  title: string
  body: string
  tone: TodayVerdictTone
}

export function todayVerdict(
  geoPercentile?: number | null,
  volPercentile?: number | null,
  volUnavailable?: boolean,
  stressRegime?: string | null,
): TodayVerdictContent {
  if (volUnavailable) {
    return {
      title: 'Partial picture today',
      body: 'News risk is live but the vol model is still warming up. Treat the combined score as incomplete — focus on headlines and market pulse below.',
      tone: 'muted',
    }
  }

  const quadrant = stressQuadrantId(geoPercentile, volPercentile, volUnavailable)
  const regime = (stressRegime ?? '').toUpperCase()

  if (quadrant === 'calm') {
    return {
      title: 'Conditions look normal',
      body: 'News risk and market vol are both below typical stress levels. No change to a long-term SIP plan is suggested based on today’s signals.',
      tone: 'clear',
    }
  }
  if (quadrant === 'geo') {
    return {
      title: 'Headlines are hot, markets are calm',
      body: 'News-driven risk is elevated but NIFTY vol is still moderate. This gap often closes — avoid pausing SIPs or panic selling on headlines alone.',
      tone: 'watch',
    }
  }
  if (quadrant === 'vol') {
    return {
      title: 'Markets are nervous, headlines are moderate',
      body: 'Volatility is elevated with calmer news flow — often a correction rather than a geopolitical regime shift. Stay disciplined with your plan.',
      tone: 'watch',
    }
  }
  if (regime === 'HIGH_STRESS') {
    return {
      title: 'Headlines and markets both stressed',
      body: 'News risk and market vol are aligned at elevated levels. Worth checking how your holdings are exposed — but stopping SIPs rarely helps long-term investors.',
      tone: 'alert',
    }
  }
  return {
    title: 'Elevated combined stress',
    body: 'Both signals are above median. Review your portfolio context below before making lump-sum decisions — routine SIPs can usually continue.',
    tone: 'watch',
  }
}

export function verdictToneClass(tone: TodayVerdictTone): string {
  if (tone === 'alert') return 'border-[var(--corridor-accent-alert)] bg-[var(--corridor-accent-alert)]/10'
  if (tone === 'watch') return 'border-[var(--corridor-accent-watch)] bg-[var(--corridor-accent-watch)]/10'
  if (tone === 'clear') return 'border-[var(--corridor-accent-clear)] bg-[var(--corridor-accent-clear)]/10'
  return 'border-white/15 bg-[#0d0d0d]'
}

export function titleAccent(tone: TodayVerdictTone, mutedClass = 'text-corridor-muted'): string {
  if (tone === 'alert') return 'text-corridor-alert'
  if (tone === 'watch') return 'text-corridor-watch'
  if (tone === 'clear') return 'text-corridor-clear'
  return mutedClass
}

export function changeClass(pct: number): string {
  if (pct > 0) return 'text-corridor-clear'
  if (pct < 0) return 'text-corridor-alert'
  return 'text-corridor-muted'
}

export function corridorPlainEnglish(corridorId?: string | null): string {
  const id = (corridorId ?? '').toLowerCase()
  const lines: Record<string, string> = {
    strait_of_hormuz: 'Persian Gulf route — affects oil imports, freight costs, and energy-linked stocks.',
    red_sea_suez: 'Red Sea / Suez lane — shipping delays and insurance costs can ripple into import prices.',
    strait_of_malacca: 'Malacca Strait — key Asia trade chokepoint; goods and electronics supply chains.',
    cape_of_good_hope: 'Cape route — longer shipping times when Suez is stressed; freight and timing risk.',
    india_china_lac: 'India–China border — defence and industrial sentiment; limited direct trade but high news weight.',
    taiwan_south_china_sea: 'South China Sea — electronics supply chains and regional tension spillovers.',
    india_pakistan_attari: 'India–Pakistan border crossing — regional trade and security headlines.',
    imec: 'India–Middle East–Europe corridor — long-horizon trade infrastructure exposure.',
    instc_chabahar: 'Chabahar / INSTC — Central Asia and Iran-adjacent trade routing.',
  }
  return lines[id] ?? 'Trade-route stress that can affect imports, freight, and commodity-linked sectors.'
}

export type TransmissionChannel = 'oil_rupee' | 'risk_off' | null

export type TransmissionState = {
  channels: TransmissionChannel[]
  label: string
  detail: string
  tone: 'clear' | 'watch' | 'alert'
}

export function computeTransmission(quotes: Array<{ key: string; change_pct: number }>): TransmissionState {
  const byKey = new Map(quotes.map((q) => [q.key, q.change_pct]))
  const brent = byKey.get('brent') ?? 0
  const usdInr = byKey.get('usd_inr') ?? 0
  const vix = byKey.get('india_vix') ?? 0
  const nifty = byKey.get('nifty') ?? 0

  const channels: TransmissionChannel[] = []
  if (brent > 0.3 && usdInr > 0.05) channels.push('oil_rupee')
  if (vix > 0.5 && nifty < -0.1) channels.push('risk_off')

  if (channels.length >= 2) {
    return {
      channels,
      label: 'Multi-channel stress',
      detail: 'Oil, rupee, and equity vol are moving together — corrections often linger longer than headline-only spikes.',
      tone: 'alert',
    }
  }
  if (channels.includes('oil_rupee')) {
    return {
      channels,
      label: 'Oil–rupee channel active',
      detail: 'Brent and USD/INR are both moving adversely — watch import costs, inflation headlines, and energy-linked sectors.',
      tone: 'watch',
    }
  }
  if (channels.includes('risk_off')) {
    return {
      channels,
      label: 'Risk-off in equities',
      detail: 'India VIX is up while NIFTY is down — classic risk-off session; often noise for long-term SIP holders.',
      tone: 'watch',
    }
  }
  return {
    channels: [],
    label: 'No synced shock detected',
    detail: 'Brent, rupee, VIX, and NIFTY are not all moving adversely together today.',
    tone: 'clear',
  }
}

export function transmissionToneClass(tone: TransmissionState['tone']): string {
  if (tone === 'alert') return 'text-corridor-alert'
  if (tone === 'watch') return 'text-corridor-watch'
  return 'text-corridor-clear'
}

export function whatChangedLine(
  geoChange7d?: number | null,
  indexDays?: number | null,
  quotes?: Array<{ key: string; label: string; change_pct: number }>,
): string {
  const parts: string[] = []
  if (indexDays != null && indexDays < 8) {
    parts.push('News risk 7d change needs 8+ index days')
  } else if (geoChange7d != null) {
    parts.push(`News risk ${geoChange7d >= 0 ? 'up' : 'down'} ${Math.abs(geoChange7d).toFixed(1)}% over 7 days`)
  }
  const movers = (quotes ?? [])
    .filter((q) => ['brent', 'usd_inr', 'india_vix', 'nifty'].includes(q.key))
    .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
  const top = movers[0]
  if (top && Math.abs(top.change_pct) >= 0.05) {
    parts.push(`${top.label} ${top.change_pct >= 0 ? '+' : ''}${top.change_pct.toFixed(2)}% today`)
  }
  return parts.length ? parts.join(' · ') : 'Waiting for market and news updates…'
}

export function formatGeoChange7d(change?: number | null, indexDays?: number | null): string {
  if (indexDays != null && indexDays < 8) {
    return `Early index (${indexDays}d)`
  }
  if (change == null) return '—'
  return `${change > 0 ? '+' : ''}${change}%`
}

export function topNewsTheme(events?: Array<{ nlp_themes?: string }>): string {
  const raw = events?.[0]?.nlp_themes?.trim()
  if (!raw) return '—'
  const first = raw.split(',')[0]?.trim()
  return first || raw.slice(0, 48)
}

export function drivingHeadlineSummary(events?: Array<{ source?: string }>): {
  count: string
  latestSource: string
} {
  const count = events?.length ?? 0
  return {
    count: count ? String(count) : '—',
    latestSource: events?.[0]?.source ?? '—',
  }
}
