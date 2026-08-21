// Home page's module picker: a grid of link-cards, one per page/module,
// grouped into "core" (bigger, highlighted) and "advanced" (smaller, dimmer)
// tiers — driven by the list in lib/modules.ts.
import { Link } from 'react-router-dom'
import { modules } from '../lib/modules'

const coreModules = modules.filter((m) => m.tier === 'core')
const advancedModules = modules.filter((m) => m.tier === 'advanced')

function ModuleCard({ mod }: { mod: (typeof modules)[number] }) {
  const isCore = mod.tier === 'core'
  return (
    <Link
      to={mod.to}
      className={`corridor-panel p-6 flex flex-col gap-4 h-full hover:bg-white/[0.03] transition-colors group ${
        isCore ? 'border-l-2 border-white/30' : 'opacity-80'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className={`corridor-kicker ${!isCore ? 'text-corridor-muted/60' : ''}`}>{mod.kicker}</span>
        <span className="material-symbols-outlined text-corridor-muted group-hover:text-white transition-colors text-[22px]">
          {mod.icon}
        </span>
      </div>
      <div className="space-y-2 flex-grow">
        <h3 className="corridor-headline text-base text-white">{mod.title}</h3>
        <p className="text-sm text-corridor-muted leading-relaxed">{mod.description}</p>
      </div>
      <span className="corridor-kicker text-white/50 group-hover:text-white transition-colors">Open module →</span>
    </Link>
  )
}

export default function Modules() {
  return (
    <section id="section-02" className="home-modules-section pt-10 pb-16 px-margin-page max-w-container-max mx-auto border-t border-white/10">
      <header className="mb-stack-md space-y-2">
        <span className="corridor-kicker">Choose a view</span>
        <h2 className="corridor-display font-headline-lg text-headline-lg">Platform modules</h2>
      </header>

      <div className="space-y-gutter">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-gutter">
          {coreModules.map((mod) => (
            <ModuleCard key={mod.to} mod={mod} />
          ))}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-gutter lg:max-w-3xl">
          {advancedModules.map((mod) => (
            <ModuleCard key={mod.to} mod={mod} />
          ))}
        </div>
      </div>
    </section>
  )
}
