import type { FormEvent } from 'react'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'

export interface FilePickerProps {
  fileId: number | undefined
  fileName: string | undefined
  onSubmit: (id: number) => void
}

export function FilePicker({ fileId, fileName, onSubmit }: FilePickerProps) {
  const [value, setValue] = useState(fileId != null ? String(fileId) : '')

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const parsed = Number(value.trim())
    if (!Number.isInteger(parsed) || parsed <= 0) return
    onSubmit(parsed)
  }

  return (
    <form onSubmit={submit} className="mb-[var(--space-3)] flex flex-wrap items-end gap-[var(--space-1)]">
      <Field label="File" htmlFor="assistant-file-id" hint={fileName ?? 'Use an already uploaded file. Seed is 1.'}>
        <Input
          id="assistant-file-id"
          inputMode="numeric"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="File id"
          aria-label="File id"
        />
      </Field>
      <Button type="submit" variant="secondary" size="sm">
        Load
      </Button>
    </form>
  )
}
