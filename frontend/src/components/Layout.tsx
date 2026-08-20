import type { ReactNode } from 'react'
import AppChrome from './AppChrome'
import Footer from './Footer'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="font-body-md text-on-surface min-h-screen bg-[#050505] corridor-page">
      <AppChrome />
      <main className="pt-[var(--chrome-height)]">{children}</main>
      <Footer />
    </div>
  )
}
