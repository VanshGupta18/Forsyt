import { Link } from 'react-router-dom'
import HeroGlobe from './HeroGlobe'
import HomeLivePulse from './HomeLivePulse'
import { HOME_DISCLAIMER, HOME_EYEBROW, HOME_SUBTITLE, HOME_TITLE } from '../lib/homeCopy'

const CTAS = [
  { to: '/news', label: 'Headlines' },
  { to: '/macroeconomics', label: 'Market stress' },
  { to: '/trade-corridor', label: 'Corridor risk' },
] as const

export default function Hero() {
  return (
    <section id="section-01" className="max-w-container-max mx-auto px-margin-page pt-8 pb-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12 items-center min-h-[min(72vh,680px)]">
        <div className="space-y-6 order-2 md:order-1">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            {HOME_EYEBROW}
          </span>

          <h1 className="corridor-display font-headline-lg text-headline-lg text-on-surface">{HOME_TITLE}</h1>

          <p className="font-body-lg text-body-lg text-corridor-muted max-w-lg">{HOME_SUBTITLE}</p>

          <p className="text-xs text-corridor-muted/80 max-w-lg">{HOME_DISCLAIMER}</p>

          <div className="flex flex-wrap gap-3">
            {CTAS.map(({ to, label }, i) => (
              <Link
                key={to}
                to={to}
                className={`corridor-btn px-5 py-2.5 text-sm ${i === 0 ? 'bg-white text-black hover:bg-white/90' : ''}`}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>

        <div className="order-1 md:order-2 flex justify-center md:justify-end items-center">
          <HeroGlobe className="w-full max-w-[min(100%,520px)] aspect-square" />
        </div>
      </div>

      <HomeLivePulse />
    </section>
  )
}
