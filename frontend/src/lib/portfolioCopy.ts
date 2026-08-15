/** Sector sensitivity guidance for portfolio exposure page — regime-driven, not holdings-specific. */

export type SectorSensitivity = {
  sector: string
  tilt: 'headwind' | 'tailwind' | 'mixed'
  note: string
}

export type PortfolioStressContext = {
  title: string
  detail: string
}

export function portfolioStressContext(
  stressParam?: string | null,
  corridorId?: string | null,
  geoRegime?: string | null,
): PortfolioStressContext {
  const stress = (stressParam ?? '').toLowerCase()
  const regime = (geoRegime ?? '').toUpperCase()

  if (stress === 'high') {
    return {
      title: 'You arrived from elevated combined stress',
      detail: 'Headlines and market vol were aligned on the stress monitor. Review sector tilts below — this is context, not a sell signal.',
    }
  }
  if (stress === 'geo') {
    return {
      title: 'You arrived from headline-led stress',
      detail: 'News risk was hot while markets were calmer. Import-heavy and energy-linked sectors often feel this first.',
    }
  }
  if (corridorId) {
    return {
      title: 'Corridor context from stress monitor',
      detail: `Trade-route focus: ${corridorId.replace(/_/g, ' ')}. See sector notes for typical transmission paths.`,
    }
  }
  if (regime === 'HIGH' || regime === 'ELEVATED') {
    return {
      title: 'Elevated geopolitical regime',
      detail: 'News risk is above normal. Use sector tilts as a checklist, not trading instructions.',
    }
  }
  return {
    title: 'Portfolio exposure context',
    detail: 'Sector sensitivity shifts with geopolitical regime. Holdings analysis is illustrative until you connect holdings.',
  }
}

export function sectorSensitivityByRegime(
  geoRegime?: string | null,
  topCorridor?: string | null,
): SectorSensitivity[] {
  const regime = (geoRegime ?? '').toUpperCase()
  const corridor = (topCorridor ?? '').toLowerCase()
  const elevated = regime === 'HIGH' || regime === 'ELEVATED'

  const base: SectorSensitivity[] = [
    {
      sector: 'Energy & oil marketing',
      tilt: elevated || corridor.includes('hormuz') || corridor.includes('red_sea') ? 'headwind' : 'mixed',
      note: 'Crude and freight shocks raise input costs; margins depend on pricing power.',
    },
    {
      sector: 'IT & exporters (USD revenue)',
      tilt: elevated ? 'tailwind' : 'mixed',
      note: 'Rupee weakness can help USD earners — offset if global risk-off hits clients.',
    },
    {
      sector: 'Banks & financials',
      tilt: elevated ? 'mixed' : 'tailwind',
      note: 'Rate and liquidity headlines matter; avoid treating all banks as one bucket.',
    },
    {
      sector: 'Consumer & autos',
      tilt: elevated ? 'headwind' : 'mixed',
      note: 'Import costs and sentiment hit discretionary demand in stress episodes.',
    },
    {
      sector: 'Defence & domestic infra',
      tilt: corridor.includes('lac') || corridor.includes('pakistan') ? 'tailwind' : 'mixed',
      note: 'Border and security headlines can lift defence sentiment; verify fundamentals separately.',
    },
    {
      sector: 'Pharma & healthcare',
      tilt: 'mixed',
      note: 'Mostly domestic demand; watch rupee on imported inputs.',
    },
  ]

  return base
}

export function tiltClass(tilt: SectorSensitivity['tilt']): string {
  if (tilt === 'headwind') return 'text-corridor-alert'
  if (tilt === 'tailwind') return 'text-corridor-clear'
  return 'text-corridor-watch'
}

export function tiltLabel(tilt: SectorSensitivity['tilt']): string {
  if (tilt === 'headwind') return 'Typical headwind'
  if (tilt === 'tailwind') return 'Possible offset'
  return 'Mixed'
}
