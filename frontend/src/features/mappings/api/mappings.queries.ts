import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { loadAllPages, withWindow, type LoadedList } from '@/lib/api/pagination'
import type { Page } from '@/lib/api/types'
import { mappingKeys } from '@/features/mappings/api/mappings.keys'
import type { Mapping, MappingCreateRequest } from '@/features/mappings/types'

export const mappingQueries = {
  detail: (mappingId: number) =>
    queryOptions({
      queryKey: mappingKeys.detail(mappingId),
      queryFn: () => apiClient.get<Mapping>(`/mappings/${mappingId}`),
    }),
  list: (dataSourceId?: number) =>
    queryOptions({
      queryKey: mappingKeys.list(dataSourceId),
      // An envelope, not a bare array: its `total` says when to stop.
      queryFn: () => {
        const path = dataSourceId === undefined ? '/mappings' : `/mappings?data_source_id=${dataSourceId}`
        return loadAllPages(async (limit, offset) => {
          const page = await apiClient.get<Page<Mapping>>(withWindow(path, limit, offset))
          return { items: page.items, total: page.total }
        })
      },
      // A backend deployed before #52 answers 404 here. Fail fast to the
      // caller's fallback instead of retrying an error the user cannot fix.
      retry: false,
    }),
}

export function useMappingsQuery(dataSourceId?: number) {
  return useQuery(mappingQueries.list(dataSourceId))
}

export function useMappingQuery(mappingId: number | null) {
  return useQuery({ ...mappingQueries.detail(mappingId ?? 0), enabled: mappingId !== null })
}

/**
 * `POST /mappings` -> 201, or 422 carrying every validation error at once.
 *
 * This is the seam between the assistant and the import wizard: the AI routes
 * stop at a `proposal_id`, and an import run needs a `mapping_id`. Saving the
 * proposal's document here is what bridges the two, and going through this
 * mutation is what makes the new mapping appear in the wizard's select — the
 * invalidation below is the whole point of sharing `mappingKeys`.
 */
export function useCreateMappingMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: MappingCreateRequest) => apiClient.post<Mapping>('/mappings', body),
    onSuccess: (mapping) => {
      queryClient.setQueryData(mappingKeys.detail(mapping.id), mapping)
      queryClient.setQueryData(
        mappingKeys.list(mapping.data_source_id),
        (current: LoadedList<Mapping> | undefined): LoadedList<Mapping> => {
          // No list cached yet: its total is unknown, not 1.
          if (current == null) return { items: [mapping], total: null, truncated: false }
          if (current.items.some((item) => item.id === mapping.id)) return current
          const total = current.total === null ? null : current.total + 1
          return { ...current, items: [mapping, ...current.items], total }
        },
      )
      void queryClient.invalidateQueries({ queryKey: mappingKeys.all })
    },
  })
}
