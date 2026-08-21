import { QueryClient } from '@tanstack/react-query'

// TanStack Query ("react-query") is a data-fetching/caching library. Instead
// of every component managing its own `loading`/`error`/`data` state and
// remembering to re-fetch at the right time, a component just calls
// `useQuery({ queryKey, queryFn })` and react-query handles: caching the
// result under `queryKey` (so switching pages and coming back doesn't
// re-fetch instantly), de-duplicating identical requests fired at the same
// time, automatically retrying failed requests, and re-fetching on a timer
// if `refetchInterval` is set. `queryClient` below is the single shared
// store all of that lives in — it's created once here and handed to every
// component via <QueryClientProvider> in main.tsx.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // How long a cached response is considered "fresh" before react-query
      // will bother re-fetching it in the background: 5 minutes. Within that
      // window, re-visiting a page reuses the cached data instantly instead
      // of showing a loading spinner.
      staleTime: 5 * 60_000,
      // Don't automatically re-fetch just because the browser tab regained
      // focus — most pages already poll on their own schedule below.
      refetchOnWindowFocus: false,
      // If a request fails, retry it once before giving up and showing an error.
      retry: 1,
    },
  },
})

// `queryKey` is how react-query tells requests apart in its cache — two
// components calling useQuery with the same key share the same cached data
// and the same in-flight request. Centralizing the keys here (instead of
// typing array literals inline everywhere) avoids typos causing two
// "supposedly identical" queries to silently not share a cache entry.
export const queryKeys = {
  health: ['health'] as const,
  home: ['pages', 'home'] as const,
  macro: ['pages', 'macro'] as const,
  news: (limit: number) => ['pages', 'news', limit] as const,
  corridor: (corridor: string | null, limit: number) => ['pages', 'corridor', corridor, limit] as const,
  portfolio: ['pages', 'portfolio'] as const,
  quality: (refresh: boolean) => ['pages', 'quality', refresh] as const,
}
