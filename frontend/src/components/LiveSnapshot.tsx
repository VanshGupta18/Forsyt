import { useEffect, useState } from 'react'
import Reveal from './Reveal'
import { fetchGprCurrent, fetchHealth } from '../lib/api'

type Kpi = {
  label: string
  value: string
  suffix?: string
  footnote: string
  footnoteClass: string
  valueClass: string
  trend: 'up' | 'down' | 'neutral'
}

const trendIcon = {
  up: 'trending_up',
  down: 'trending_down',
  neutral: 'remove',
}

const fallbackKpis: Kpi[] = [
  {
    label: 'India GPR Index',
    value: '—',
    suffix: '/100',
    footnote: 'Connect API for live GPR',
    footnoteClass: 'text-tertiary',
    valueClass: 'text-primary',
    trend: 'neutral',
  },
  {
    label: 'Articles Indexed',
    value: '—',
    footnote: 'PostgreSQL news pipeline',
    footnoteClass: 'text-secondary',
    valueClass: '',
    trend: 'neutral',
  },
  {
    label: 'GPR 7-Day Average',
    value: '—',
    suffix: '/100',
    footnote: 'Smoothed daily index',
    footnoteClass: 'text-on-surface-variant',
    valueClass: 'text-primary',
    trend: 'neutral',
  },
  {
    label: 'Data As Of',
    value: '—',
    footnote: 'Latest GPR observation',
    footnoteClass: 'text-on-surface-variant',
    valueClass: 'text-primary',
    trend: 'neutral',
  },
]

export default function LiveSnapshot() {
  const [kpis, setKpis] = useState<Kpi[]>(fallbackKpis)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [gpr, health] = await Promise.all([
          fetchGprCurrent().catch(() => null),
          fetchHealth().catch(() => null),
        ])
        if (cancelled) return

        const gprVal = gpr?.gpr_index != null ? Math.round(gpr.gpr_index) : null
        const ma7 = gpr?.gpr_7ma != null ? Math.round(gpr.gpr_7ma) : null
        const articles = health?.total_articles ?? gpr?.total_articles

        setKpis([
          {
            label: 'India GPR Index',
            value: gprVal != null ? String(gprVal) : '—',
            suffix: '/100',
            footnote: gpr?.date ? `As of ${gpr.date}` : 'Medium-High Risk band',
            footnoteClass: 'text-tertiary',
            valueClass: 'text-primary',
            trend: 'up',
          },
          {
            label: 'Articles Indexed',
            value: articles != null ? String(articles) : '—',
            footnote: health?.status === 'healthy' ? 'Live PostgreSQL feed' : 'News pipeline',
            footnoteClass: 'text-secondary',
            valueClass: '',
            trend: 'up',
          },
          {
            label: 'GPR 7-Day Average',
            value: ma7 != null ? String(ma7) : '—',
            suffix: '/100',
            footnote: 'Rolling geopolitical baseline',
            footnoteClass: 'text-on-surface-variant',
            valueClass: 'text-primary',
            trend: 'neutral',
          },
          {
            label: 'Data As Of',
            value: gpr?.date ?? '—',
            footnote: 'From /api/gpr/current',
            footnoteClass: 'text-on-surface-variant',
            valueClass: 'text-primary',
            trend: 'neutral',
          },
        ])
      } catch {
        if (!cancelled) setKpis(fallbackKpis)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="py-stack-lg px-margin-page max-w-container-max mx-auto">
      <Reveal>
        <h2 className="font-headline-md text-on-surface mb-stack-md flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
          Live India Snapshot
        </h2>
      </Reveal>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter">
        {kpis.map((kpi, i) => (
          <Reveal key={kpi.label} delay={i * 80}>
            <div className="glass-card glass-card-hover p-6 rounded-xl inner-glow h-full">
              <div className="flex items-center justify-between mb-2">
                <p className="font-label-md text-on-surface-variant">{kpi.label}</p>
                <span
                  className={`material-symbols-outlined text-[16px] ${kpi.footnoteClass}`}
                  aria-hidden="true"
                >
                  {trendIcon[kpi.trend]}
                </span>
              </div>
              <div className="flex items-end justify-between">
                <div>
                  <span className={`text-display-lg text-[36px] font-bold tabular-nums ${kpi.valueClass}`}>
                    {kpi.value}
                  </span>
                  {kpi.suffix && <span className="text-on-surface-variant">{kpi.suffix}</span>}
                </div>
              </div>
              <p className={`font-label-md mt-4 ${kpi.footnoteClass}`}>{kpi.footnote}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
