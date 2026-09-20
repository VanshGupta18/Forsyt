// Toggle panel for the corridor map's optional overlay layers — the small
// dark "LAYERS" card in the top-left, styled after the WorldMonitor panel.
import { useState } from 'react'
import { OVERLAY_LAYERS } from '../lib/mapLayers'

export default function MapLayerPanel({
  active,
  onToggle,
}: {
  active: Set<string>
  onToggle: (key: string) => void
}) {
  const [open, setOpen] = useState(true)

  return (
    <div className="absolute top-3 left-3 z-20 w-52 bg-black/85 backdrop-blur-sm border border-white/10 text-white select-none">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-white/70 hover:text-white"
      >
        <span>Layers</span>
        <span className={`transition-transform ${open ? '' : '-rotate-90'}`}>▾</span>
      </button>
      {open && (
        <div className="border-t border-white/10">
          {OVERLAY_LAYERS.map((l) => {
            const on = active.has(l.key)
            return (
              <button
                key={l.key}
                type="button"
                onClick={() => onToggle(l.key)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-white/5"
              >
                <span
                  className="w-3.5 h-3.5 shrink-0 border flex items-center justify-center text-[9px] leading-none"
                  style={{ borderColor: on ? l.color : 'rgba(255,255,255,0.3)', background: on ? l.color : 'transparent', color: '#000' }}
                >
                  {on ? '✓' : ''}
                </span>
                <span aria-hidden>{l.icon}</span>
                <span className={on ? 'text-white' : 'text-white/60'}>{l.label}</span>
                <span className="ml-auto w-4 h-0.5 rounded-sm" style={{ background: on ? l.color : 'transparent' }} />
              </button>
            )
          })}
          <p className="px-3 py-1.5 text-[9px] text-white/35 border-t border-white/10">Approximate routes · illustrative</p>
        </div>
      )}
    </div>
  )
}
