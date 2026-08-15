import { Link } from 'react-router-dom'
import { formatCorridorName } from '../lib/api'
import { corridorPlainEnglish } from '../lib/macroCopy'

type Props = {
  corridorId?: string | null
}

export default function TopCorridorCard({ corridorId }: Props) {
  if (!corridorId) return null

  const label = formatCorridorName(corridorId)
  const detail = corridorPlainEnglish(corridorId)
  const href = `/trade-corridor?corridor=${encodeURIComponent(corridorId.toLowerCase())}`

  return (
    <div className="corridor-panel p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <p className="corridor-kicker">Trade route context</p>
        <h2 className="corridor-headline mt-1 text-base">Most stressed route: {label}</h2>
        <p className="text-sm text-corridor-muted mt-2 max-w-xl">{detail}</p>
      </div>
      <Link to={href} className="corridor-btn px-4 py-2 text-sm shrink-0 text-center">
        See route details →
      </Link>
    </div>
  )
}
