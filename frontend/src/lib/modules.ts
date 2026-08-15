import { CORRIDOR_PAGE_SUBTITLE } from './corridorCopy'
import { MACRO_PAGE_SUBTITLE } from './macroCopy'
import { NEWS_PAGE_SUBTITLE } from './newsCopy'

export type ModuleTier = 'core' | 'advanced'

export const modules: {
  to: string
  title: string
  description: string
  icon: string
  tier: ModuleTier
  kicker: string
}[] = [
  {
    to: '/news',
    title: 'News Intelligence',
    description: NEWS_PAGE_SUBTITLE,
    icon: 'newspaper',
    tier: 'core',
    kicker: 'Headlines',
  },
  {
    to: '/macroeconomics',
    title: 'Indian Market Stress Monitor',
    description: MACRO_PAGE_SUBTITLE,
    icon: 'bar_chart',
    tier: 'core',
    kicker: 'Markets',
  },
  {
    to: '/trade-corridor',
    title: 'Trade & Corridor Risk',
    description: CORRIDOR_PAGE_SUBTITLE,
    icon: 'directions_boat',
    tier: 'core',
    kicker: 'Routes',
  },
  {
    to: '/portfolio-exposure',
    title: 'Portfolio Exposure & GPR Analytics',
    description:
      'Assess portfolio exposure using India GPR Index with scenario analysis, stress testing and sector impact.',
    icon: 'deployed_code',
    tier: 'advanced',
    kicker: 'Advanced',
  },
  {
    to: '/quality',
    title: 'Platform Quality & Accuracy',
    description:
      'Validate GPR index accuracy, corridor tagging precision and NLP coverage against live benchmarks.',
    icon: 'verified',
    tier: 'advanced',
    kicker: 'Advanced',
  },
]
