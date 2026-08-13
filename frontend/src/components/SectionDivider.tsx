export default function SectionDivider() {
  return (
    <div className="flex flex-col items-center py-6" aria-hidden>
      <div className="h-14 w-px bg-white/10" />
      <div className="flex items-center justify-center w-9 h-9 rotate-45 border border-white/15 rounded-md bg-surface-container-lowest">
        <span className="material-symbols-outlined -rotate-45 text-on-surface-variant text-[16px]">bolt</span>
      </div>
      <div className="h-14 w-px bg-white/10" />
    </div>
  )
}
