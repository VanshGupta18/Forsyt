type Props = {
  message: string
  onRetry?: () => void
}

export default function ApiErrorBanner({ message, onRetry }: Props) {
  return (
    <div className="rounded-lg border border-[#f59e0b]/40 bg-[#f59e0b]/10 px-4 py-3 text-sm text-[#f59e0b] flex items-center justify-between gap-4">
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="text-white underline hover:no-underline shrink-0">
          Retry
        </button>
      )}
    </div>
  )
}
