import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import ForsytLogo from './ForsytLogo'
import { fetchHealth } from '../lib/api'
import { queryKeys } from '../lib/queryClient'

export default function Footer() {
  const { data: health } = useQuery({
    queryKey: queryKeys.health,
    queryFn: fetchHealth,
    staleTime: 2 * 60_000,
  })

  const healthy = health ? health.status === 'healthy' : null

  const statusLabel =
    healthy === null ? 'Checking data feed…' : healthy ? 'Data feed live' : 'Data feed degraded'

  return (
    <footer className="app-footer corridor-page border-t border-[var(--chrome-border)] bg-[var(--chrome-bg)]">
      <div className="max-w-container-max mx-auto px-margin-page py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/" className="shrink-0 hover:opacity-80 transition-opacity">
            <ForsytLogo variant="mark" />
          </Link>
          <p className="text-[11px] text-corridor-muted leading-snug truncate">
            © 2026 Forsyt · Not trading or shipping advice
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-corridor-muted sm:justify-end">
          <Link to="/quality" className="hover:text-white transition-colors">
            Quality
          </Link>
          <span className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 shrink-0 ${
                healthy === false ? 'bg-corridor-alert' : healthy ? 'bg-corridor-clear' : 'bg-corridor-muted'
              }`}
            />
            {statusLabel}
          </span>
        </div>
      </div>
    </footer>
  )
}
