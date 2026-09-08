import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { mappingsKeys } from '@/features/mappings/api/mappings.keys'
import type { Mapping } from '@/features/mappings/types'

function mappingsListOptions() {
  return queryOptions({
    queryKey: mappingsKeys.list(),
    queryFn: () => apiClient.get<Mapping[]>('/mappings'),
  })
}

export function useMappingsQuery() {
  return useQuery(mappingsListOptions())
}
