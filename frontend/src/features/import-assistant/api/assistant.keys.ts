// `/ai/providers` lives under `systemKeys` — the shell and the studio share it.
export const assistantKeys = {
  all: ['import-assistant'] as const,
  proposal: (id: number) => [...assistantKeys.all, 'proposal', id] as const,
}
