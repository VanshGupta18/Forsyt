import { Link } from 'react-router-dom'

type Props = {
  label: string
  value: string
  valueClass?: string
  href?: string
}

export default function PulseCard({ label, value, valueClass = 'text-white', href }: Props) {
  const inner = (
    <>
      <span className="corridor-kicker">{label}</span>
      <span className={`corridor-score text-2xl ${valueClass}`}>{value}</span>
    </>
  )

  if (href) {
    return (
      <Link to={href} className="corridor-panel shrink-0 min-w-[140px] p-3 flex flex-col gap-1 hover:bg-white/5 transition-colors">
        {inner}
      </Link>
    )
  }

  return <div className="corridor-panel shrink-0 min-w-[140px] p-3 flex flex-col gap-1">{inner}</div>
}
