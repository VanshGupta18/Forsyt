import { useEffect, useState } from 'react'

const SECTION_IDS = ['section-01', 'section-02', 'section-03', 'section-04', 'section-05', 'section-06']

export default function PageRail() {
  const [active, setActive] = useState(0)

  useEffect(() => {
    const targets = SECTION_IDS.map((id) => document.getElementById(id)).filter(
      (el): el is HTMLElement => el !== null,
    )
    if (!targets.length) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (!visible.length) return
        const mostVisible = visible.reduce((a, b) => (a.intersectionRatio > b.intersectionRatio ? a : b))
        const idx = targets.findIndex((el) => el === mostVisible.target)
        if (idx !== -1) setActive(idx)
      },
      { threshold: [0.2, 0.4, 0.6], rootMargin: '-15% 0px -50% 0px' },
    )
    targets.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  return (
    <div className="hidden xl:flex fixed left-8 top-1/2 -translate-y-1/2 z-30 flex-col gap-6" aria-hidden>
      {SECTION_IDS.map((id, i) => (
        <a
          key={id}
          href={`#${id}`}
          className={`font-label-md transition-colors duration-300 ${
            i === active ? 'text-primary' : 'text-on-surface-variant/30'
          }`}
        >
          {String(i + 1).padStart(2, '0')}
        </a>
      ))}
    </div>
  )
}
