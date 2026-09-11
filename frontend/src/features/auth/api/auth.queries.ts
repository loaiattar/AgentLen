import { queryOptions, useQuery } from '@tanstack/react-query'

import { meRequest } from '@/features/auth/api/auth.api'
import { authKeys } from '@/features/auth/api/auth.keys'
import { getSessionToken } from '@/lib/auth/session'

export const authQueries = {
  me: () =>
    queryOptions({
      queryKey: authKeys.me(),
      queryFn: meRequest,
      enabled: Boolean(getSessionToken()),
      retry: false,
    }),
}

export function useMeQuery() {
  return useQuery(authQueries.me())
}
