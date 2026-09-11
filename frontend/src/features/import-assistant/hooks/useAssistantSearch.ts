import { usePipelineSearch } from '@/features/imports/hooks/usePipelineSearch'

/** Studio leaf of the shared import pipeline search. */
export function useAssistantSearch() {
  return usePipelineSearch('/import-assistant')
}
