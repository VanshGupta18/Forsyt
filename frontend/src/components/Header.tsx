import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import logo from '../assets/forsyt-logo.png'

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/news', label: 'News Intelligence' },
  { to: '/macroeconomics', label: 'Indian Macroeconomics' },
  { to: '/trade-corridor', label: 'Trade & Corridor Risk' },
  { to: '/portfolio-exposure', label: 'Portfolio Exposure' },
  { to: '/about', label: 'About' },
]

export default function Header() {
  const [scrolled, setScrolled] = useState(false)

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
        <button className="btn-primary text-on-primary-container font-label-md px-6 py-2.5 rounded-lg flex items-center gap-1.5">
          Explore Platform
          <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
        </button>
      </div>
    </header>
  )
}
