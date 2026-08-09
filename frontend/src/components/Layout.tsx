import type { ReactNode } from 'react'
import VantaWavesBackground from './VantaWavesBackground'
import Header from './Header'
import Footer from './Footer'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="font-body-md text-on-surface min-h-screen">
      <VantaWavesBackground />
      <div className="noise-overlay" />
      <Header />
      <main className="pt-20">{children}</main>
      <Footer />
    </div>
  )
}
