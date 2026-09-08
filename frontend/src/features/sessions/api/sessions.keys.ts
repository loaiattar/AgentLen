export const sessionsKeys = {
  all: ['sessions'] as const,
  detail: (sessionId: string) => [...sessionsKeys.all, 'detail', sessionId] as const,
}
