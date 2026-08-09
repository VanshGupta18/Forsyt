import { useEffect, useState } from 'react'

function formatUTC(date: Date) {
  const day = date.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' }).toUpperCase()
  const rest = date
    .toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
    .toUpperCase()
  const time = date.toLocaleTimeString('en-GB', { hour12: false, timeZone: 'UTC' })
  return `${day}, ${rest} ${time} UTC`
}

export default function LiveClock({ className }: { className?: string }) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <span className={className ?? 'font-label-md text-[11px] text-on-surface-variant tracking-wider'}>
      {formatUTC(now)}
    </span>
  )
}
