import HeroGlobeVideo from './HeroGlobeVideo'

export default function Hero() {
  return (
    <section className="relative h-[850px] flex items-center px-margin-page max-w-container-max mx-auto overflow-hidden">
      <div className="w-full lg:w-1/2 z-10 space-y-7">
        <div className="eyebrow-badge fade-in-up" style={{ animationDelay: '0ms' }}>
          <span className="eyebrow-dot" />
          Live Intelligence Platform
        </div>

        <h1
          className="font-display-lg text-[52px] leading-[1.05] text-on-surface fade-in-up"
          style={{ animationDelay: '80ms' }}
        >
          See geopolitical risks <br />
          before they{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-container via-primary to-primary-container">
            impact India.
          </span>
        </h1>

        <p
          className="font-body-lg text-body-lg text-on-surface-variant max-w-lg fade-in-up"
          style={{ animationDelay: '160ms' }}
        >
          Real-time intelligence. Actionable insights. Stronger decision-making for sovereign
          entities and global investors.
        </p>

        <div className="flex gap-4 pt-4 fade-in-up" style={{ animationDelay: '240ms' }}>
          <button className="btn-primary text-on-primary-container px-8 py-4 rounded-lg font-title-lg flex items-center gap-2">
            Explore Platform
            <span className="material-symbols-outlined">arrow_forward</span>
          </button>
          <button className="btn-secondary px-8 py-4 rounded-lg font-title-lg text-on-surface">
            View Live Risk
          </button>
        </div>

        <div className="flex items-center gap-6 pt-6 fade-in-up" style={{ animationDelay: '320ms' }}>
          <div className="flex -space-x-2">
            {['#4d8eff', '#4edea3', '#ffb95f', '#ff8a80'].map((c) => (
              <span
                key={c}
                className="h-7 w-7 rounded-full border-2 border-surface"
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <p className="font-label-md text-label-md text-on-surface-variant">
            Trusted by <span className="text-on-surface font-semibold">40+</span> sovereign &amp; institutional desks
          </p>
        </div>
      </div>

      <div className="absolute inset-y-0 right-0 hidden lg:flex w-3/5 items-center justify-between gap-4 pr-8 pl-4">
        <div className="flex-1 flex items-center justify-center pointer-events-none min-w-0">
          <HeroGlobeVideo className="h-[640px] w-[640px] max-w-full" />
        </div>

        <div className="flex flex-col gap-4 shrink-0">
          <div
            className="glass-card glass-card-hover p-4 rounded-xl w-48 inner-glow fade-in-up"
            style={{ animationDelay: '400ms' }}
          >
            <span className="font-label-md text-on-surface-variant uppercase">Live Global Events</span>
            <div className="flex items-baseline gap-2">
              <span className="text-headline-lg font-bold">34</span>
              <span className="text-secondary text-sm">Active</span>
            </div>
          </div>
          <div
            className="glass-card glass-card-hover p-4 rounded-xl w-48 inner-glow fade-in-up"
            style={{ animationDelay: '480ms' }}
          >
            <span className="font-label-md text-error uppercase">Risk Signal</span>
            <div className="flex items-baseline gap-2">
              <span className="text-headline-lg font-bold">Elevated</span>
            </div>
          </div>
        </div>
      </div>

      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 opacity-60 fade-in-up" style={{ animationDelay: '700ms' }}>
        <span className="font-label-md text-[10px] text-on-surface-variant uppercase tracking-widest">Scroll</span>
        <span className="material-symbols-outlined text-on-surface-variant animate-bounce text-[18px]">
          expand_more
        </span>
      </div>
    </section>
  )
}
