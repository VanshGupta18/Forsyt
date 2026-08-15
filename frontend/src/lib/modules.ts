import macroImg from '../assets/module-macro.jpg'
import tradeImg from '../assets/module-trade.jpg'
import portfolioImg from '../assets/module-portfolio.jpg'

export const modules = [
  {
    to: '/news',
    title: 'News Intelligence',
    description:
      'Editorial geopolitical intelligence — Tier-ranked headlines, GPR context, morning brief, and corridor-scoped filters.',
    icon: 'newspaper',
    image: tradeImg,
  },
  {
    to: '/macroeconomics',
    title: 'Indian Market Stress Monitor',
    description:
      'Dual-signal intelligence combining geopolitical news risk and NIFTY volatility — honest context for Indian markets.',
    icon: 'bar_chart',
    image: macroImg,
  },
  {
    to: '/trade-corridor',
    title: 'Trade & Corridor Risk',
    description:
      'Monitor global trade routes, chokepoints, supply chains and corridor disruptions impacting India.',
    icon: 'directions_boat',
    image: tradeImg,
  },
  {
    to: '/portfolio-exposure',
    title: 'Portfolio Exposure & GPR Analytics',
    description:
      'Assess portfolio exposure using India GPR Index with scenario analysis, stress testing and sector impact.',
    icon: 'deployed_code',
    image: portfolioImg,
  },
  {
    to: '/quality',
    title: 'Platform Quality & Accuracy',
    description:
      'Validate GPR index accuracy, corridor tagging precision and NLP coverage against live benchmarks.',
    icon: 'verified',
    image: macroImg,
  },
]
