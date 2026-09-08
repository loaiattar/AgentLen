import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { mappingsKeys } from '@/features/mappings/api/mappings.keys'
import type { CreateMappingInput, Mapping } from '@/features/mappings/types'

export function useCreateMappingMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: CreateMappingInput) => apiClient.post<Mapping>('/mappings', input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mappingsKeys.all })
    },
  })
}
