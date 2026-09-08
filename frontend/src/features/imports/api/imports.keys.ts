export const importsKeys = {
  all: ['imports'] as const,
  list: () => [...importsKeys.all, 'list'] as const,
  detail: (importId: string) => [...importsKeys.all, 'detail', importId] as const,
}
