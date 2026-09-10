import type { PageParams } from '@/features/imports/types'

export const importKeys = {
  all: ['imports'] as const,
  list: (params: PageParams) => [...importKeys.all, 'list', params] as const,
  detail: (importRunId: number) => [...importKeys.all, 'detail', importRunId] as const,
  issues: (importRunId: number, severity: string | undefined, params: PageParams) =>
    [...importKeys.all, 'issues', importRunId, severity ?? 'all', params] as const,
}

export const fileKeys = {
  all: ['files'] as const,
  detail: (fileId: number) => [...fileKeys.all, 'detail', fileId] as const,
  profile: (fileId: number) => [...fileKeys.all, 'profile', fileId] as const,
}

export const dataSourceKeys = {
  all: ['data-sources'] as const,
  list: () => [...dataSourceKeys.all, 'list'] as const,
}

export const mappingKeys = {
  all: ['mappings'] as const,
  list: (dataSourceId: number | undefined) =>
    [...mappingKeys.all, 'list', dataSourceId ?? 'any'] as const,
}
