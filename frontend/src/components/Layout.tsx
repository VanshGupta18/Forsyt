// Shared page shell used by every route (see App.tsx): header (AppChrome),
// the page's own content in the middle, and the footer.
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
