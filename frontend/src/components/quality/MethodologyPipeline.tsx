// Quality page's "how we build scores" section: 4 numbered step cards
// (Collect → Tag → Build → Validate) plus a decorative signal-flow strip
// below them. All copy/colors come from lib/qualityCopy.ts and lib/qualityVisuals.ts.
import { METHODOLOGY_STEPS } from '../../lib/qualityCopy'
import { FLOW_PIPELINE_NODES, METHODOLOGY_STEP_THEMES } from '../../lib/qualityVisuals'

export default function MethodologyPipeline() {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {METHODOLOGY_STEPS.map((step, i) => {
          const theme = METHODOLOGY_STEP_THEMES[i] ?? METHODOLOGY_STEP_THEMES[0]
          return (
            <article
              key={step.step}
              className="quality-method-card corridor-panel p-5 flex flex-col gap-3 border border-white/[0.06]"
            >
              <div
                className="w-11 h-11 rounded-full flex items-center justify-center corridor-score text-sm font-bold mx-auto sm:mx-0"
                style={{
                  background: theme.bg,
                  border: `2px solid ${theme.border}`,
                  color: theme.text,
                }}
              >
                {String(step.step).padStart(2, '0')}
              </div>
              <h3 className="font-body-md text-white font-semibold text-center sm:text-left">{step.title}</h3>
              <p className="text-xs text-corridor-muted leading-relaxed text-center sm:text-left flex-1">
                {step.body}
              </p>
              <span
                className="corridor-kicker text-[9px] pt-2 border-t border-white/5 text-center sm:text-left"
                style={{ color: theme.text }}
              >
                {step.layer}
              </span>
            </article>
          )
        })}
      </div>

      {/* NERAI-style signal flow strip */}
      <div className="quality-flow-strip relative py-8 px-4">
        <div className="absolute left-8 right-8 top-1/2 h-px bg-white/10 -translate-y-1/2 hidden sm:block" />
        <div className="relative flex flex-col sm:flex-row justify-between items-center gap-8 sm:gap-4">
          {FLOW_PIPELINE_NODES.map((node, i) => (
            <div key={node.id} className="flex flex-col items-center gap-2 z-10 min-w-[120px]">
              <span className="corridor-kicker text-[9px]" style={{ color: node.color }}>
                {node.label}
              </span>
              <div
                className="w-14 h-14 rounded-full flex items-center justify-center quality-flow-node"
                style={{
                  background: `${node.color}22`,
                  boxShadow: `0 0 24px ${node.color}33`,
                  border: `2px solid ${node.color}`,
                }}
              >
                <span
                  className="w-6 h-6 rounded-full"
                  style={{ background: node.color }}
                />
              </div>
              <span className="text-[10px] text-corridor-muted text-center">{node.sub}</span>
              {i < FLOW_PIPELINE_NODES.length - 1 && (
                <div className="quality-flow-dots hidden sm:flex absolute" style={{ left: `${25 + i * 25}%` }} aria-hidden />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
