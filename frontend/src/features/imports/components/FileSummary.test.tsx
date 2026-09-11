import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { FileSummary } from '@/features/imports/components/FileSummary'
import type { FileUpload } from '@/features/imports/types'
import { renderWithRouter } from '@/test/router'

const FILE: FileUpload = {
  id: 7,
  original_name: 'trace.jsonl',
  format: 'jsonl',
  size_bytes: 2048,
  content_hash: 'a'.repeat(64),
  already_seen: false,
  previous_import_run_ids: [],
}

function renderSummary(file: FileUpload, onAcknowledge = vi.fn()) {
  renderWithRouter(() => (
    <FileSummary file={file} profile={null} acknowledged={false} onAcknowledge={onAcknowledge} onReplace={vi.fn()} />
  ))
}

describe('FileSummary', () => {
  it.each([true, false])('warns about nothing for a file never imported (already_seen: %s)', async (alreadySeen) => {
    // The bug this pins: `GET /files/{id}` answered `already_seen: true` for
    // every file, so a reload warned about a brand-new upload.
    renderSummary({ ...FILE, already_seen: alreadySeen })

    expect(await screen.findByText('trace.jsonl')).toBeInTheDocument()
    expect(screen.queryByText(/already been imported/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Import it anyway' })).toBeNull()
  })

  it('warns and asks for an acknowledgement when a past run imported the file', async () => {
    const onAcknowledge = vi.fn()
    renderSummary({ ...FILE, already_seen: false, previous_import_run_ids: [11, 12] }, onAcknowledge)

    expect(await screen.findByText('This file has already been imported.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '#11' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '#12' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Import it anyway' }))

    expect(onAcknowledge).toHaveBeenCalledOnce()
  })
})
