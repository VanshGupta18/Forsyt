// Hand-drawn inline SVG icon (an "F" stem plus a curved meridian line) — the
// app's logo is drawn as vector shapes here, not loaded from an image file.
type Props = {
  className?: string
}

/** Shared monogram paths — F stem + meridian arc, stroke-only, no blob frame */
export default function ForsytLogoMark({ className = 'w-5 h-5' }: Props) {
  return (
    <svg
      viewBox="0 0 20 20"
      className={`shrink-0 text-white ${className}`}
      fill="none"
      aria-hidden
    >
      <path d="M4 3h8M4 3v14M4 10h5.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="square" />
      <path
        d="M11.5 4.5c2.8 1.6 2.8 9.4 0 11"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        opacity="0.65"
      />
    </svg>
  )
}
