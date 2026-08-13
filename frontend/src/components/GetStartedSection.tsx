import { Link } from 'react-router-dom'
import Reveal from './Reveal'

const COLUMNS = [
  {
    label: 'For Analysts & Investors',
    description: 'Explore live GPR, corridor risk, and dual-signal dashboards.',
    to: '/macroeconomics',
    cta: 'Explore Platform',
  },
  {
    label: 'For Researchers',
    description: 'Review benchmark validation, accuracy metrics, and methodology.',
    to: '/quality',
    cta: 'View Validation',
  },
]

export default function GetStartedSection() {
  return (
    <section id="section-06" className="py-stack-lg px-margin-page max-w-container-max mx-auto pb-32">
      <Reveal className="text-center mb-stack-lg space-y-2">
        <h2 className="font-headline-lg text-on-surface">Get started with Forsyt</h2>
        <p className="font-body-md text-on-surface-variant">
          Built for the people who read the market and the people who model it.
        </p>
      </Reveal>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter">
        {COLUMNS.map((col, i) => (
          <Reveal key={col.label} delay={i * 100}>
            <div className="border border-white/10 rounded-lg p-8 h-full flex flex-col gap-4 bg-surface-container-lowest/40">
              <h3 className="font-headline-md text-on-surface uppercase tracking-wide">{col.label}</h3>
              <p className="font-body-md text-on-surface-variant flex-grow">{col.description}</p>
              <Link
                to={col.to}
                className="btn-secondary px-6 py-3 rounded-lg font-label-md text-on-surface text-center uppercase tracking-wide w-fit"
              >
                {col.cta}
              </Link>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
