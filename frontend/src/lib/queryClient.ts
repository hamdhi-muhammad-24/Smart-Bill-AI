import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 3000,          // 3 seconds data freshness: Instant tab switching & navigation
      gcTime: 1000 * 60 * 10,   // 10 minutes memory garbage collection
    },
  },
})

