import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export const queryKeys = {
  health: ['health'] as const,
  home: ['pages', 'home'] as const,
  macro: ['pages', 'macro'] as const,
  news: (limit: number) => ['pages', 'news', limit] as const,
  corridor: (corridor: string | null, limit: number) => ['pages', 'corridor', corridor, limit] as const,
  portfolio: ['pages', 'portfolio'] as const,
  quality: (refresh: boolean) => ['pages', 'quality', refresh] as const,
}
