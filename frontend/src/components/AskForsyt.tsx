// AskForsyt — a chat box over the India-relative analyst agent (POST /api/ask).
// Minimal request/response transcript; server degrades gracefully when the
// LLM/agent isn't configured, so this always gets an answer.
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { askForsyt, type AskAnswer } from '../lib/api'

type Turn = { q: string; a: string; source?: AskAnswer['source'] }

const COUNTRY_SUGGESTIONS = [
  'Compare India\'s risk with China vs Pakistan',
  'What is driving India–Iran risk right now?',
  'Which tracked country is the highest risk to India?',
]

export default function AskForsyt({
  title = 'India-relative analyst',
  suggestions = COUNTRY_SUGGESTIONS,
  placeholder = "Ask about a country's risk to India…",
}: { title?: string; suggestions?: string[]; placeholder?: string }) {
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])

  const ask = useMutation({
    mutationFn: (q: string) => askForsyt(q),
    onSuccess: (res, q) => setTurns((t) => [...t, { q, a: res.answer, source: res.source }]),
    onError: (err, q) =>
      setTurns((t) => [...t, { q, a: `Error: ${(err as Error).message}` }]),
  })

  function submit(q: string) {
    const question = q.trim()
    if (!question || ask.isPending) return
    setInput('')
    ask.mutate(question)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="font-label-md uppercase tracking-wide text-[10px] text-corridor-muted">
        Ask Forsyt — {title}
      </div>

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="rounded border border-white/15 px-2 py-1 text-[11px] text-white/70 hover:border-corridor-watch hover:text-white"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-3">
        {turns.map((t, i) => (
          <div key={i} className="flex flex-col gap-1">
            <div className="text-xs font-medium text-white/90">{t.q}</div>
            <div className="text-sm leading-relaxed text-white/80">{t.a}</div>
            {t.source && t.source !== 'agent' && (
              <div className="text-[10px] text-corridor-muted">({t.source} answer)</div>
            )}
          </div>
        ))}
        {ask.isPending && <div className="text-xs text-corridor-muted">Thinking…</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(input)
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          className="flex-1 rounded border border-white/15 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-corridor-muted focus:border-corridor-watch focus:outline-none"
        />
        <button
          type="submit"
          disabled={ask.isPending || !input.trim()}
          className="rounded bg-white px-3 py-2 text-sm font-medium text-black disabled:opacity-40"
        >
          Ask
        </button>
      </form>
      <p className="text-[10px] text-corridor-muted">Not investment advice.</p>
    </div>
  )
}
