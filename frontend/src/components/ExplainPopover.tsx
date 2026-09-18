// "Why this number" — renders an exact additive attribution (or SHAP) contract
// as a small popover: the formula, one contribution bar per term, and a caveat.
// Every explained number on the platform reuses this one component.
import { useState } from 'react'
import type { Explanation } from '../lib/api'

// Green = pulls the number DOWN (tailwind / lowers risk), red = pushes it UP
// (headwind / raises risk), grey = ~neutral. Matches the app's tile colors.
function barColor(contribution: number): string {
  if (contribution > 0.05) return '#ef4444'
  if (contribution < -0.05) return '#00c853'
  return '#737373'
}

export default function ExplainPopover({
  explain,
  label = 'Why?',
  align = 'right',
}: {
  explain?: Explanation
  label?: string
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  if (!explain || !explain.terms?.length) return null

  const maxAbs = Math.max(...explain.terms.map((t) => Math.abs(t.contribution)), 1e-6)

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-[10px] uppercase tracking-wide text-gray-400 hover:text-white border border-white/15 rounded px-1.5 py-0.5"
      >
        ⓘ {label}
      </button>
      {open && (
        <>
          {/* click-away layer */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div
            className={`absolute z-50 mt-1 w-72 bg-[#0d0d0d] border border-white/15 rounded-md p-3 font-mono text-left normal-case tracking-normal shadow-xl ${
              align === 'right' ? 'right-0' : 'left-0'
            }`}
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-[11px] text-white font-semibold">
                = {explain.output}
              </span>
              <span className="text-[9px] uppercase text-gray-500">
                {explain.method === 'shap' ? 'SHAP' : 'exact'}
              </span>
            </div>
            <div className="text-[10px] text-gray-400 mb-3 leading-snug">{explain.formula}</div>
            <div className="space-y-2">
              {explain.terms.map((t) => (
                <div key={t.label}>
                  <div className="flex items-baseline justify-between text-[11px]">
                    <span className="text-gray-300 truncate">{t.label}</span>
                    <span style={{ color: barColor(t.contribution) }}>
                      {t.contribution > 0 ? '+' : ''}
                      {t.contribution}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-white/5 rounded-sm overflow-hidden mt-0.5">
                    <div
                      className="h-full rounded-sm"
                      style={{
                        width: `${(Math.abs(t.contribution) / maxAbs) * 100}%`,
                        background: barColor(t.contribution),
                      }}
                    />
                  </div>
                  {t.note && <div className="text-[9px] text-gray-600 mt-0.5">{t.note}</div>}
                </div>
              ))}
            </div>
            {explain.caveat && (
              <div className="text-[9px] text-gray-600 mt-3 pt-2 border-t border-white/10 leading-snug">
                {explain.caveat}
              </div>
            )}
          </div>
        </>
      )}
    </span>
  )
}
