// The "FORSYT" brand logo, in three variants: just the mark (icon), just the
// wordmark (text), or both together ("lockup", the default).
import ForsytLogoMark from './ForsytLogoMark'

type Props = {
  variant?: 'lockup' | 'mark' | 'wordmark'
  className?: string
}

export default function ForsytLogo({ variant = 'lockup', className = '' }: Props) {
  if (variant === 'mark') {
    return (
      <span className={`inline-flex ${className}`}>
        <ForsytLogoMark />
      </span>
    )
  }

  if (variant === 'wordmark') {
    return (
      <span className={`corridor-display text-base tracking-[0.08em] text-white leading-none ${className}`}>
        FORSYT
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <ForsytLogoMark />
      <span className="corridor-display text-base tracking-[0.08em] text-white leading-none">FORSYT</span>
    </span>
  )
}
