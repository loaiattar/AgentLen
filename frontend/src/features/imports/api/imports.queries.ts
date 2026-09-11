import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { dataSourceKeys, fileKeys, importKeys } from '@/features/imports/api/imports.keys'
import {
  isTerminal,
  type DataSource,
  type FileProfile,
  type FileUpload,
  type ImportCreateRequest,
  type ImportCreateResponse,
  type ImportIssue,
  type ImportPreview,
  type ImportPreviewRequest,
  type ImportSeverity,
  type ImportStatus,
  type Page,
  type PageParams,
} from '@/features/imports/types'

/** API.md §5 suggests a 1s interval while a run is still moving. */
export const IMPORT_POLL_INTERVAL_MS = 1000

function toQueryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

// --- Files -------------------------------------------------------------------

export const fileQueries = {
  detail: (fileId: number) =>
    queryOptions({
      queryKey: fileKeys.detail(fileId),
      queryFn: () => apiClient.get<FileUpload>(`/files/${fileId}`),
    }),
}

export function useFileQuery(fileId: number | null) {
  return useQuery({ ...fileQueries.detail(fileId ?? 0), enabled: fileId !== null })
}

/**
 * `POST /files` — multipart. The client passes the FormData through untouched
 * so the browser sets its own boundary header.
 */
export function useUploadFileMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return apiClient.post<FileUpload>('/files', body)
    },
    onSuccess: (upload) => {
      queryClient.setQueryData(fileKeys.detail(upload.id), upload)
    },
  })
}

/**
 * `POST /files/{id}/profile` — a POST because it computes, but the result is
 * stable for a stored file, so it is seeded into the cache under its own key.
 */
export function useProfileFileMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (fileId: number) => apiClient.post<FileProfile>(`/files/${fileId}/profile`),
    onSuccess: (profile) => {
      queryClient.setQueryData(fileKeys.profile(profile.file_id), profile)
    },
  })
}

// --- Data sources ------------------------------------------------------------

export const dataSourceQueries = {
  /** `GET /data-sources` returns a bare array, not a paginated envelope. */
  list: () =>
    queryOptions({
      queryKey: dataSourceKeys.list(),
      queryFn: () => apiClient.get<DataSource[]>('/data-sources'),
    }),
}

export function useDataSourcesQuery() {
  return useQuery(dataSourceQueries.list())
}

export function useCreateDataSourceMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: { slug: string; name: string; description?: string | null }) =>
      apiClient.post<DataSource>('/data-sources', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dataSourceKeys.all })
    },
  })
}

// --- Imports -----------------------------------------------------------------

/** Dry-run. Writes nothing — the gate before the real launch. */
export function usePreviewImportMutation() {
  return useMutation({
    mutationFn: (body: ImportPreviewRequest) =>
      apiClient.post<ImportPreview>('/imports/preview', body),
  })
}

/** `POST /imports` -> 202. The worker picks the run up; poll `GET /imports/{id}`. */
export function useCreateImportMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: ImportCreateRequest) =>
      apiClient.post<ImportCreateResponse>('/imports', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: importKeys.all })
    },
  })
}

export const importQueries = {
  list: (params: PageParams = {}) =>
    queryOptions({
      queryKey: importKeys.list(params),
      queryFn: () =>
        apiClient.get<Page<ImportStatus>>(
          `/imports${toQueryString({ limit: params.limit, offset: params.offset })}`,
        ),
    }),
  detail: (importRunId: number) =>
    queryOptions({
      queryKey: importKeys.detail(importRunId),
      queryFn: () => apiClient.get<ImportStatus>(`/imports/${importRunId}`),
    }),
  issues: (importRunId: number, severity: ImportSeverity | undefined, params: PageParams = {}) =>
    queryOptions({
      queryKey: importKeys.issues(importRunId, severity, params),
      queryFn: () =>
        apiClient.get<Page<ImportIssue>>(
          `/imports/${importRunId}/issues${toQueryString({
            severity,
            limit: params.limit,
            offset: params.offset,
          })}`,
        ),
    }),
}

export function useImportsQuery(params: PageParams = {}) {
  return useQuery(importQueries.list(params))
}

/**
 * Polls until the run reaches a terminal status, then stops on its own — a
 * finished report never changes, so there is nothing left to ask for.
 */
export function useImportQuery(importRunId: number | null) {
  return useQuery({
    ...importQueries.detail(importRunId ?? 0),
    enabled: importRunId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === undefined) return IMPORT_POLL_INTERVAL_MS
      return isTerminal(status) ? false : IMPORT_POLL_INTERVAL_MS
    },
  })
}

export function useImportIssuesQuery(
  importRunId: number | null,
  severity?: ImportSeverity,
  params: PageParams = {},
) {
  return useQuery({
    ...importQueries.issues(importRunId ?? 0, severity, params),
    enabled: importRunId !== null,
  })
}
