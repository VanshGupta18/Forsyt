import logo from '../assets/forsyt-logo.png'

export default function Footer() {
  return (
    <footer className="relative bg-surface-container-lowest border-t border-white/5 py-stack-lg">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
      <div className="px-margin-page max-w-container-max mx-auto flex flex-col md:flex-row justify-between items-center gap-stack-md">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <img alt="FORSYT Logo" className="h-8 w-auto" src={logo} />
            <span className="font-headline-md text-on-surface">FORSYT</span>
          </div>
          <p className="font-body-md text-on-surface-variant">
            © 2026 FORSYT Intelligence. Empowering sovereign decision-making.
          </p>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary shadow-[0_0_6px_1px_rgba(78,222,163,0.6)] animate-pulse" />
            <span className="font-label-md text-[11px] text-on-surface-variant uppercase tracking-wider">
              All systems operational
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-8 justify-center">
          {['Privacy Policy', 'Terms of Service', 'Security Architecture', 'Contact Support'].map((label) => (
            <a
              key={label}
              className="relative font-body-md text-on-surface-variant hover:text-primary transition-colors after:absolute after:left-0 after:-bottom-1 after:h-px after:w-0 after:bg-primary after:transition-all after:duration-300 hover:after:w-full"
              href="#"
            >
              {label}
            </a>
          ))}
        </div>
      </div>
    </footer>
  )
}
