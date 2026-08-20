import { DATA_ARCHITECTURE_LAYERS } from '../../lib/qualityCopy'

const LAYER_COLORS = ['#4a90d9', '#4edea3', '#f5b800', '#adc6ff']

export default function DataArchitectureDiagram() {
  return (
    <div className="corridor-panel p-6 overflow-x-auto quality-arch-diagram">
      <div className="flex flex-col gap-6 min-w-[min(100%,720px)]">
        <div className="flex flex-col sm:flex-row sm:items-stretch gap-1 sm:gap-0 relative">
          {DATA_ARCHITECTURE_LAYERS.map((layer, i) => (
            <div key={layer.id} className="flex sm:flex-1 items-center gap-0 relative group">
              <div
                className="flex-1 p-4 flex flex-col gap-2 border border-white/[0.06] bg-[#111111] quality-arch-layer transition-colors hover:bg-[#151515]"
                style={{ borderTopColor: LAYER_COLORS[i], borderTopWidth: 2 }}
              >
                <span className="corridor-kicker text-[9px]" style={{ color: LAYER_COLORS[i] }}>
                  {layer.tag}
                </span>
                <span className="font-body-md text-white text-sm font-semibold">{layer.label}</span>
              </div>
              {i < DATA_ARCHITECTURE_LAYERS.length - 1 && (
                <div className="hidden sm:flex items-center px-1 shrink-0 relative w-8 justify-center">
                  <div className="w-full h-px bg-white/15 relative overflow-visible">
                    {[0, 1, 2].map((d) => (
                      <span
                        key={d}
                        className="quality-arch-dot absolute top-1/2 -translate-y-1/2 w-1 h-1 rounded-full"
                        style={{
                          background: LAYER_COLORS[i],
                          animationDelay: `${d * 0.5 + i * 0.3}s`,
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        <p className="text-[10px] text-corridor-muted text-center uppercase tracking-widest">
          Open sources in · proprietary indices out · every value traceable
        </p>
      </div>
    </div>
  )
}
