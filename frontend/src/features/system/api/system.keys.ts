export const systemKeys = {
  all: ['system'] as const,
  aiProviders: () => [...systemKeys.all, 'ai-providers'] as const,
  readiness: () => [...systemKeys.all, 'readiness'] as const,
}
