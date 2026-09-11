/**
 * The single set of cache keys for mappings.
 *
 * Both halves of the mapping story read the same list — the import wizard to
 * pick one, the assistant to show what it just saved — so they must invalidate
 * through the same keys. A second set declared elsewhere would leave a freshly
 * accepted mapping invisible in the wizard's select until a reload.
 */
export const mappingKeys = {
  all: ['mappings'] as const,
  list: (dataSourceId: number | undefined) =>
    [...mappingKeys.all, 'list', dataSourceId ?? 'any'] as const,
  detail: (mappingId: number) => [...mappingKeys.all, 'detail', mappingId] as const,
}
