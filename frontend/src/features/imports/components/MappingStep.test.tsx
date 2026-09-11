import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MappingStep } from '@/features/imports/components/MappingStep'
import type { LoadedList } from '@/lib/api/pagination'

const lists = vi.hoisted(() => ({
  sources: undefined as unknown as LoadedList<unknown>,
  mappings: undefined as unknown as LoadedList<unknown>,
}))

function loaded(data: unknown) {
  return { isPending: false, isError: false, error: null, data }
}

vi.mock('@/features/imports/api/imports.queries', () => ({
  useDataSourcesQuery: () => loaded(lists.sources),
}))

vi.mock('@/features/mappings/api/mappings.queries', () => ({
  useMappingsQuery: () => loaded(lists.mappings),
  useMappingQuery: () => loaded(undefined),
}))

function source(id: number) {
  return { id, slug: `source-${id}`, name: `Source ${id}` }
}

function mapping(id: number) {
  return { id, name: `Mapping ${id}`, version: 1, status: 'active' }
}

function renderStep() {
  render(
    <MappingStep fileId={null} dataSourceId={1} mappingId={null} onDataSourceChange={vi.fn()} onMappingChange={vi.fn()} />,
  )
}

beforeEach(() => {
  lists.sources = { items: [source(1), source(2)], total: 2, truncated: false }
  lists.mappings = { items: [mapping(1)], total: 1, truncated: false }
})

describe('MappingStep list truncation', () => {
  it('says nothing when both lists are complete', () => {
    renderStep()

    expect(screen.getAllByRole('option', { name: /Source \d/ })).toHaveLength(2)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('warns that some data sources are not offered', () => {
    lists.sources = { items: [source(1), source(2)], total: 2345, truncated: true }

    renderStep()

    expect(screen.getByRole('status')).toHaveTextContent('Showing 2 of 2,345 data sources.')
  })

  it('warns that some mappings are not offered', () => {
    lists.mappings = { items: [mapping(1)], total: null, truncated: true }

    renderStep()

    expect(screen.getByRole('status')).toHaveTextContent('Showing the first 1 mappings: the API reported no total.')
  })
})
