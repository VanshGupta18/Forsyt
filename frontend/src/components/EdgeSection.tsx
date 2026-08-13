import Reveal from './Reveal'

const LAYERS = [
  { label: 'Data Sources', sub: '9 Indian news sources — RSS feeds & scrapers' },
  { label: 'NLP & Scoring', sub: 'NER, sentiment, sector & corridor tagging' },
  { label: 'GPR Index & API', sub: 'Daily index, corridor scores, dual-signal' },
]

const CHECKLIST = [
  'Automated news aggregation',
  'NLP event extraction',
  'Daily India GPR index',
  'Corridor risk board',
  'Dual-signal dashboard',
  'Historical event overlays',
]

export default function EdgeSection() {
  return (
    <section id="section-02" className="py-stack-lg px-margin-page max-w-container-max mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-gutter items-center">
        <Reveal className="space-y-3 w-full max-w-md mx-auto lg:mx-0">
          {LAYERS.map((layer, i) => (
            <div
              key={layer.label}
              className="border border-white/10 rounded-lg p-5 bg-surface-container-lowest/40"
              style={{ marginLeft: `${i * 28}px` }}
            >
              <p className="font-label-md text-primary uppercase tracking-wide">{layer.label}</p>
              <p className="font-body-md text-on-surface-variant text-sm mt-1">{layer.sub}</p>
            </div>
          ))}
        </Reveal>

        <Reveal delay={100} className="space-y-6">
          <span className="eyebrow-badge">
            <span className="eyebrow-dot" />
            Platform Architecture
          </span>
          <h2 className="font-headline-lg text-on-surface">Giving India an edge</h2>
          <p className="font-body-md text-on-surface-variant max-w-md">
            Forsyt is built as a pipeline, not a dashboard bolted onto a spreadsheet — from raw news to a
            validated, corridor-aware risk signal.
          </p>
          <ul className="space-y-3">
            {CHECKLIST.map((item) => (
              <li key={item} className="flex items-center gap-3 font-label-md text-on-surface-variant uppercase tracking-wide">
                <span className="material-symbols-outlined text-secondary text-[18px]">check</span>
                {item}
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  )
}
