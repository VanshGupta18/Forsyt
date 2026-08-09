import Reveal from './Reveal'

const kpis = [
  {
    label: 'India GPR Index',
    value: '67',
    suffix: '/100',
    footnote: 'Medium-High Risk',
    footnoteClass: 'text-tertiary',
    valueClass: 'text-primary',
    trend: 'up' as const,
  },
  {
    label: 'Active Global Events',
    value: '34',
    footnote: '+12 vs yesterday',
    footnoteClass: 'text-secondary',
    valueClass: '',
    trend: 'up' as const,
  },
  {
    label: 'Countries Under Watch',
    value: '92',
    footnote: 'Across 6 continents',
    footnoteClass: 'text-on-surface-variant',
    valueClass: 'text-primary',
    trend: 'neutral' as const,
  },
  {
    label: '7-Day Risk Outlook',
    value: '+8%',
    footnote: 'Risk increasing',
    footnoteClass: 'text-error',
    valueClass: 'text-error',
    trend: 'up' as const,
  },
]

const trendIcon = {
  up: 'trending_up',
  down: 'trending_down',
  neutral: 'remove',
}

export default function LiveSnapshot() {
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
