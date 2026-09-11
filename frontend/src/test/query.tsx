import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

/**
 * A client with the production defaults that matter, and retries off.
 *
 * `staleTime: 30s` and `refetchOnWindowFocus: false` are kept because they are
 * exactly what made the issues query in the wizard never ask again: a hook that
 * looks like it polls, under these defaults, does not. A test client without
 * them would pass while the real one fails.
 *
 * `retry` is the one deliberate difference — the production client retries
 * once, which would make every error test wait for a second request that adds
 * nothing to what is being asserted.
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000,
        refetchOnWindowFocus: false,
        retry: false,
      },
      mutations: { retry: false },
    },
  })
}

export function withQueryClient(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}
