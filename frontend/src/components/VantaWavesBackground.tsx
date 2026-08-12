import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import VantaWavesImport from 'vanta/dist/vanta.waves.min.js'

type VantaEffect = { destroy: () => void }
type VantaWavesFn = (options: Record<string, unknown>) => VantaEffect

function resolveVantaWaves(mod: unknown): VantaWavesFn {
  let current: unknown = mod
  while (current && typeof current !== 'function') {
    current = (current as { default?: unknown }).default
  }
  if (typeof current !== 'function') {
    throw new Error('vanta WAVES effect failed to load')
  }
  return current as VantaWavesFn
}

const WAVES = resolveVantaWaves(VantaWavesImport)

export default function VantaWavesBackground() {
  const hostRef = useRef<HTMLDivElement>(null)
  const effectRef = useRef<VantaEffect | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host || effectRef.current) return

    effectRef.current = WAVES({
      el: host,
      THREE,
      mouseControls: true,
      touchControls: true,
      gyroControls: false,
      minHeight: 200,
      minWidth: 200,
      scale: 1,
      scaleMobile: 1,
      color: 0x8202f,
    })

    return () => {
      effectRef.current?.destroy()
      effectRef.current = null
    }
  }, [])

  return (
    <div
      ref={hostRef}
      id="vanta-waves-bg"
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-20"
    />
  )
}
