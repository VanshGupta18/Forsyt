import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import HeroGlobe from './HeroGlobe'
import { fetchGprCurrent, fetchHealth } from '../lib/api'

export default function Hero() {
  const [articles, setArticles] = useState<number | null>(null)
  const [regime, setRegime] = useState<string>('—')

  useEffect(() => {
    fetchHealth().then((h) => setArticles(h.total_articles ?? null)).catch(() => undefined)
    fetchGprCurrent()
      .then((g) => {
        const idx = g.gpr_index ?? 100
        if (idx >= 135) setRegime('Elevated')
        else if (idx >= 100) setRegime('Moderate')
        else setRegime('Calm')
      })
      .catch(() => undefined)
  }, [])

  return (
    <section id="section-01" className="relative h-[850px] flex items-center px-margin-page max-w-container-max mx-auto overflow-hidden">
      <div className="w-full lg:w-1/2 z-10 space-y-7">
        <div className="eyebrow-badge fade-in-up" style={{ animationDelay: '0ms' }}>
          <span className="eyebrow-dot" />
          Live Intelligence Platform
        </div>

        <h1 className="font-display-lg text-[52px] leading-[1.05] text-on-surface fade-in-up" style={{ animationDelay: '80ms' }}>
          See geopolitical risks <br />
          before they{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-container via-primary to-primary-container">
            impact India.
          </span>
        </h1>

        <p className="font-body-lg text-body-lg text-on-surface-variant max-w-lg fade-in-up" style={{ animationDelay: '160ms' }}>
          Real-time intelligence. Actionable insights. Stronger decision-making for sovereign entities and global investors.
        </p>

        <div className="flex gap-4 pt-4 fade-in-up" style={{ animationDelay: '240ms' }}>
          <Link to="/macroeconomics" className="btn-primary text-on-primary-container px-8 py-4 rounded-lg font-title-lg flex items-center gap-2">
            Explore Platform
            <span className="material-symbols-outlined">arrow_forward</span>
          </Link>
          <Link to="/news" className="btn-secondary px-8 py-4 rounded-lg font-title-lg text-on-surface">
            View Live Risk
          </Link>
        </div>
      </div>

      <div className="absolute inset-y-0 right-0 hidden lg:flex w-3/5 items-center justify-between gap-4 pr-8 pl-4">
        <div className="flex-1 flex items-center justify-center pointer-events-none min-w-0">
          <HeroGlobe className="h-[640px] w-[640px] max-w-full" />
        </div>

        <div className="flex flex-col gap-4 shrink-0">
          <div className="glass-card glass-card-hover p-4 rounded-xl w-48 inner-glow fade-in-up" style={{ animationDelay: '400ms' }}>
            <span className="font-label-md text-on-surface-variant uppercase">Articles indexed</span>
            <div className="flex items-baseline gap-2">
              <span className="text-headline-lg font-bold">{articles ?? '—'}</span>
              <span className="text-secondary text-sm">Live</span>
            </div>
          </div>
          <div className="glass-card glass-card-hover p-4 rounded-xl w-48 inner-glow fade-in-up" style={{ animationDelay: '480ms' }}>
            <span className="font-label-md text-error uppercase">GPR regime</span>
            <div className="flex items-baseline gap-2">
              <span className="text-headline-lg font-bold">{regime}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
