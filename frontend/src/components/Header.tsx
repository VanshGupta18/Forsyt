import { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import logo from '../assets/forsyt-logo.png'

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/news', label: 'News Intelligence' },
  { to: '/macroeconomics', label: 'Indian Macroeconomics' },
  { to: '/trade-corridor', label: 'Trade & Corridor Risk' },
  { to: '/portfolio-exposure', label: 'Portfolio Exposure' },
  { to: '/quality', label: 'Platform Quality' },
]

export default function Header() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed top-0 w-full z-50 backdrop-blur-xl border-b transition-all duration-300 ${
        scrolled
          ? 'bg-surface/90 border-white/10 shadow-[0_8px_30px_-10px_rgba(0,0,0,0.6)]'
          : 'bg-surface/50 border-white/5 shadow-none'
      }`}
    >
      <div
        className={`flex justify-between items-center px-margin-page max-w-container-max mx-auto transition-all duration-300 ${
          scrolled ? 'h-16' : 'h-20'
        }`}
      >
        <div className="flex items-center gap-4">
          <img alt="FORSYT Logo" className="h-9 w-auto" src={logo} />
          <span className="font-display-lg text-[22px] tracking-tighter text-on-surface">FORSYT</span>
          <span className="hidden lg:block h-4 w-px bg-white/15" aria-hidden />
          <span className="hidden lg:block font-label-md text-on-surface-variant/60 uppercase tracking-wider">
            Geopolitical Intelligence
          </span>
        </div>

        <nav className="hidden md:flex gap-8">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `relative pb-1 font-body-md text-[14px] transition-colors duration-300 after:absolute after:left-0 after:-bottom-[1px] after:h-[2px] after:rounded-full after:bg-primary after:transition-all after:duration-300 ${
                  isActive
                    ? 'text-primary font-semibold after:w-full'
                    : 'text-on-surface-variant hover:text-on-surface after:w-0'
                }`
              }
              end={link.to === '/'}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link to="/macroeconomics" className="hidden sm:flex btn-primary text-on-primary-container font-label-md px-6 py-2.5 rounded-lg items-center gap-1.5">
            Explore Platform
            <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
          </Link>
          <button
            type="button"
            className="md:hidden p-2 text-on-surface"
            aria-label="Open menu"
            onClick={() => setMobileOpen((o) => !o)}
          >
            <span className="material-symbols-outlined">{mobileOpen ? 'close' : 'menu'}</span>
          </button>
        </div>
      </div>

      {mobileOpen && (
        <nav className="md:hidden border-t border-white/10 bg-surface/95 px-margin-page py-4 flex flex-col gap-3">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `py-2 text-sm ${isActive ? 'text-primary font-semibold' : 'text-on-surface-variant'}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
