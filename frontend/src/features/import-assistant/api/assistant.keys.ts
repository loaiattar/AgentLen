export const assistantKeys = {
  all: ['import-assistant'] as const,
  providers: () => [...assistantKeys.all, 'providers'] as const,
  file: (id: number) => [...assistantKeys.all, 'file', id] as const,
  profile: (id: number) => [...assistantKeys.all, 'profile', id] as const,
  proposal: (id: number) => [...assistantKeys.all, 'proposal', id] as const,
}
