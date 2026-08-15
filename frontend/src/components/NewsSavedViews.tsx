import { useEffect, useRef, useState } from 'react'
import type { SavedNewsView } from '../lib/newsPrefs'

type Props = {
  savedViews: SavedNewsView[]
  onApply: (view: SavedNewsView) => void
  onSave: (name: string) => void
  onRemove: (id: string) => void
}

export default function NewsSavedViews({ savedViews, onApply, onSave, onRemove }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointer)
    return () => document.removeEventListener('mousedown', onPointer)
  }, [open])

  const handleSave = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    onSave(trimmed)
    setName('')
    setOpen(false)
  }

  return (
    <div className="ml-auto flex flex-wrap items-center gap-2">
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          className="corridor-btn px-3 py-1.5 text-xs"
          onClick={() => setOpen((v) => !v)}
        >
          Saved views{savedViews.length ? ` (${savedViews.length})` : ''}
        </button>
        {open && (
          <div className="absolute right-0 top-full z-30 mt-1 w-56 corridor-panel p-2 shadow-lg">
            {savedViews.length === 0 && (
              <p className="text-xs text-corridor-muted px-2 py-1">No saved views yet.</p>
            )}
            {savedViews.map((view) => (
              <div key={view.id} className="flex items-center gap-1">
                <button
                  type="button"
                  className="flex-1 text-left text-xs px-2 py-1.5 hover:bg-[#111111] truncate"
                  onClick={() => {
                    onApply(view)
                    setOpen(false)
                  }}
                >
                  {view.name}
                </button>
                <button
                  type="button"
                  className="text-corridor-muted hover:text-corridor-alert px-1"
                  aria-label={`Remove ${view.name}`}
                  onClick={() => onRemove(view.id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      <input
        className="corridor-input px-2 py-1.5 text-xs w-32"
        placeholder="View name…"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSave()}
      />
      <button type="button" className="corridor-btn px-3 py-1.5 text-xs" onClick={handleSave}>
        Save view
      </button>
    </div>
  )
}
