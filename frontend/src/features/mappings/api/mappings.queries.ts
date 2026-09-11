import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import type { Page } from '@/lib/api/types'
import { mappingKeys } from '@/features/mappings/api/mappings.keys'
import type { Mapping, MappingCreateRequest } from '@/features/mappings/types'

/** Enough for every seeded source; the route caps at its own maximum anyway. */
const LIST_LIMIT = 200

export const mappingQueries = {
  detail: (mappingId: number) =>
    queryOptions({
      queryKey: mappingKeys.detail(mappingId),
      queryFn: () => apiClient.get<Mapping>(`/mappings/${mappingId}`),
    }),
  list: (dataSourceId?: number) =>
    queryOptions({
      queryKey: mappingKeys.list(dataSourceId),
      queryFn: async () => {
        const search = new URLSearchParams({ limit: String(LIST_LIMIT) })
        if (dataSourceId !== undefined) search.set('data_source_id', String(dataSourceId))
        const page = await apiClient.get<Page<Mapping>>(`/mappings?${search.toString()}`)
        return page.items
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
      void queryClient.invalidateQueries({ queryKey: mappingKeys.all })
    },
  })
}
