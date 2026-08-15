import { Link } from 'react-router-dom'
import { modules } from '../lib/modules'

export default function Modules() {
  return (
    <section id="section-02" className="py-stack-lg px-margin-page max-w-container-max mx-auto pb-16">
      <header className="mb-stack-md space-y-2">
        <span className="corridor-kicker">Choose a view</span>
        <h2 className="corridor-display font-headline-lg text-headline-lg text-on-surface">Platform modules</h2>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-gutter">
        {modules.map((mod) => (
          <Link
            key={mod.to}
            to={mod.to}
            className={`corridor-panel p-6 flex flex-col gap-4 h-full hover:bg-white/[0.03] transition-colors group ${
              mod.tier === 'advanced' ? 'opacity-80' : ''
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <span className={`corridor-kicker ${mod.tier === 'advanced' ? 'text-corridor-muted/60' : ''}`}>
                {mod.kicker}
              </span>
              <span className="material-symbols-outlined text-corridor-muted group-hover:text-white transition-colors text-[22px]">
                {mod.icon}
              </span>
            </div>
            <div className="space-y-2 flex-grow">
              <h3 className="corridor-headline text-base text-white">{mod.title}</h3>
              <p className="text-sm text-corridor-muted leading-relaxed">{mod.description}</p>
            </div>
            <span className="corridor-kicker text-white/50 group-hover:text-white transition-colors">
              Open module →
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}
