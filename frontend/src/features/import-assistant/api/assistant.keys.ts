export const assistantKeys = {
  all: ['import-assistant'] as const,
  providers: () => [...assistantKeys.all, 'providers'] as const,
  proposal: (id: number) => [...assistantKeys.all, 'proposal', id] as const,
}
