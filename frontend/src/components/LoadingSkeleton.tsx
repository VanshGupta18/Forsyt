// Generic "content is loading" placeholder: a stack of pulsing gray bars,
// each one a little shorter than the last.
type Props = {
  className?: string
  lines?: number
}

export default function LoadingSkeleton({ className = '', lines = 1 }: Props) {
  return (
    <div className={`animate-pulse space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-4 bg-white/10 rounded w-full" style={{ width: `${100 - i * 15}%` }} />
      ))}
    </div>
  )
}
