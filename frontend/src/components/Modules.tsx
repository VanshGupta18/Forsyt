import { Link } from 'react-router-dom'
import Reveal from './Reveal'
import { modules } from '../lib/modules'

export default function Modules() {
  return (
    <section id="section-04" className="py-stack-lg px-margin-page max-w-container-max mx-auto pb-32">
      <Reveal className="mb-stack-lg space-y-2">
        <span className="eyebrow-badge">
          <span className="eyebrow-dot" />
          Explore the Platform
        </span>
        <h2 className="font-headline-lg text-on-surface">Precision Intelligence Modules</h2>
      </Reveal>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
        {modules.map((mod, i) => (
          <Reveal key={mod.to} delay={i * 100}>
            <div className="glass-card glass-card-hover group rounded-2xl overflow-hidden flex flex-col h-full inner-glow relative">
              <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              <div className="p-8 space-y-4 flex-grow">
                <div className="flex justify-between items-start">
                  <h3 className="font-headline-md text-on-surface leading-tight">{mod.title}</h3>
                  <span className="material-symbols-outlined text-primary-container bg-gradient-to-br from-primary-container/20 to-primary-container/5 border border-primary-container/20 p-3 rounded-lg group-hover:scale-110 transition-transform duration-300">
                    {mod.icon}
                  </span>
                </div>
                <p className="font-body-md text-on-surface-variant">{mod.description}</p>
              </div>
              <div className="relative h-64 mx-4 mb-4 rounded-xl overflow-hidden">
                <img
                  className="w-full h-full object-cover opacity-60 group-hover:opacity-85 group-hover:scale-105 transition-all duration-500 ease-out"
                  src={mod.image}
                  alt={mod.title}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
                <div className="absolute bottom-4 left-4">
                  <Link
                    to={mod.to}
                    className="bg-white/10 backdrop-blur-md border border-white/20 text-on-surface px-4 py-2 rounded-lg font-label-md flex items-center gap-2 group-hover:bg-primary group-hover:text-on-primary group-hover:gap-3 transition-all duration-300"
                  >
                    Explore Module
                    <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  </Link>
                </div>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
