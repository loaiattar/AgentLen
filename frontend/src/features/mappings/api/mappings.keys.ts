export const mappingsKeys = {
  all: ['mappings'] as const,
  lists: () => [...mappingsKeys.all, 'list'] as const,
}
