import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import WAVES from 'vanta/src/vanta.waves.js'

type VantaEffect = { destroy: () => void }

export default function VantaWavesBackground() {
  const containerRef = useRef<HTMLDivElement>(null)
  const effectRef = useRef<VantaEffect | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    effectRef.current = WAVES({
      el,
      THREE,
      mouseControls: true,
      touchControls: true,
      gyroControls: false,
      minHeight: 200.0,
      minWidth: 200.0,
      scale: 1.0,
      scaleMobile: 1.0,
      color: 0x0e1c33,
    })

    return () => {
      effectRef.current?.destroy()
      effectRef.current = null
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 -z-10 h-full w-full pointer-events-none"
      aria-hidden="true"
    />
  )
}
