import Reveal from './Reveal'

const LEFT_NODES = [
  { icon: 'speed', title: 'GPR Index', description: 'Daily normalized risk score, validated vs. Caldara-Iacoviello.' },
  { icon: 'directions_boat', title: 'Corridor Risk', description: '12 trade-route scores: Hormuz, Malacca, LAC, Red Sea.' },
  { icon: 'newspaper', title: 'Event Feed', description: 'NLP-tagged news with themes, tone and locations.' },
]

const RIGHT_NODES = [
  { icon: 'balance', title: 'Dual-Signal', description: 'Geo risk + NIFTY volatility, side by side, honestly framed.' },
  { icon: 'show_chart', title: 'Market Context', description: 'Live NIFTY, SENSEX, VIX, USD/INR and Brent quotes.' },
  { icon: 'verified', title: 'Accuracy & Validation', description: 'Benchmarked and corridor sanity-checked, not black-box.' },
]

function Node({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3 border border-white/10 rounded-lg p-4 bg-surface-container-lowest/40">
      <span className="material-symbols-outlined text-primary text-[20px]">{icon}</span>
      <div>
        <p className="font-label-md text-on-surface uppercase tracking-wide">{title}</p>
        <p className="font-body-md text-on-surface-variant text-sm mt-1">{description}</p>
      </div>
    </div>
  )
}

export default function CapabilityHub() {
  return (
    <section id="section-03" className="py-stack-lg px-margin-page max-w-container-max mx-auto">
      <Reveal className="mb-stack-lg space-y-2 text-center">
        <span className="eyebrow-badge">
          <span className="eyebrow-dot" />
          Integrated Intelligence Engine
        </span>
        <h2 className="font-headline-lg text-on-surface">Supercharge your risk workflow</h2>
        <p className="font-body-md text-on-surface-variant max-w-lg mx-auto">
          One engine accelerating geopolitical risk analysis across India's markets — from raw news to a
          validated signal analysts can act on.
        </p>
      </Reveal>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-gutter items-center">
        <Reveal className="space-y-4">
          {LEFT_NODES.map((node) => (
            <Node key={node.title} {...node} />
          ))}
        </Reveal>

        <Reveal delay={100} className="hidden lg:flex items-center justify-center px-8">
          <div className="w-16 h-16 rounded-full border border-primary/30 flex items-center justify-center bg-surface-container-lowest/60 shadow-[var(--shadow-glow-blue)]">
            <span className="material-symbols-outlined text-primary text-[28px]">bolt</span>
          </div>
        </Reveal>

        <Reveal delay={150} className="space-y-4">
          {RIGHT_NODES.map((node) => (
            <Node key={node.title} {...node} />
          ))}
        </Reveal>
      </div>
    </section>
  )
}
