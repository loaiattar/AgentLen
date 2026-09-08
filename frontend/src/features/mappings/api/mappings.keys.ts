export const mappingsKeys = {
  all: ['mappings'] as const,
  list: () => [...mappingsKeys.all, 'list'] as const,
}
