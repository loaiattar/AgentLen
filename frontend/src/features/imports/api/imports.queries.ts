import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { importsKeys } from '@/features/imports/api/imports.keys'
import type { ImportItem } from '@/features/imports/types'

function importsListOptions() {
  return queryOptions({
    queryKey: importsKeys.list(),
    queryFn: () => apiClient.get<ImportItem[]>('/imports'),
  })
}

export function useImportsQuery() {
  return useQuery(importsListOptions())
}

function importDetailOptions(importId: string) {
  return queryOptions({
    queryKey: importsKeys.detail(importId),
    queryFn: () => apiClient.get<ImportItem>(`/imports/${importId}`),
    enabled: Boolean(importId),
  })
}

export function useImportQuery(importId: string) {
  return useQuery(importDetailOptions(importId))
}
