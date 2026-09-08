import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { importsKeys } from '@/features/imports/api/imports.keys'
import type { ImportItem } from '@/features/imports/types'

export function useCreateImportMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiClient.post<ImportItem>('/imports', formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: importsKeys.all })
    },
  })
}

export function useDeleteImportMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (importId: string) => apiClient.delete<void>(`/imports/${importId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: importsKeys.all })
    },
  })
}
