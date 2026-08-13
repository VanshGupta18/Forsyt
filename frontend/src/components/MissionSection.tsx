import Reveal from './Reveal'

const PARAGRAPHS = [
  "India's financial markets are increasingly exposed to geopolitical shocks — border conflicts, sanctions, commodity shocks — yet no dedicated, real-time, India-specific intelligence platform exists.",
  "Global risk tools carry a Western bias, publish with a month's lag, and don't map risk to Indian corridors or sectors.",
  'Forsyt closes that gap: a daily GPR index built from Indian sources, validated against the Caldara-Iacoviello benchmark, mapped to the corridors and sectors that matter.',
  'This is intelligence and context, not a prediction engine. We tested whether GPR forecasts NIFTY volatility — it does not beat market data alone out of sample, and we say so plainly.',
]

export default function MissionSection() {
  return (
    <section id="section-05" className="py-stack-lg px-margin-page max-w-container-max mx-auto">
      <Reveal>
        <div className="border border-white/10 rounded-lg overflow-hidden">
          <div className="flex items-center justify-between gap-4 px-6 py-3 border-b border-white/10 bg-surface-container-lowest/60">
            <span className="font-label-md text-on-surface-variant/30 tracking-widest hidden sm:block truncate">
              ////////////////////////////
            </span>
            <span className="font-label-md text-primary uppercase tracking-widest shrink-0">// Our Mission //</span>
            <span className="font-label-md text-on-surface-variant/30 tracking-widest hidden sm:block truncate">
              ////////////////////////////
            </span>
          </div>
          <div className="p-8 md:p-12 space-y-5 max-w-2xl mx-auto text-center">
            {PARAGRAPHS.map((p) => (
              <p key={p} className="font-body-md text-on-surface-variant">
                {p}
              </p>
            ))}
          </div>
        </div>
      </Reveal>
    </section>
  )
}
