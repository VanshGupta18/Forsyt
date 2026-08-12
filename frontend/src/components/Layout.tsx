import type { ReactNode } from 'react'
import Header from './Header'
import Footer from './Footer'
import VantaWavesBackground from './VantaWavesBackground'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="font-body-md text-on-surface min-h-screen relative">
      <VantaWavesBackground />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-surface/55"
      />
      <div className="noise-overlay" />
      <Header />
      <main className="pt-20">{children}</main>
      <Footer />
    </div>
  )
}
