import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { UploadCloud } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils/cn'

/**
 * Extensions the backend's `LocalFileStorage` accepts. The real check is
 * server-side (and reads the magic bytes, not the name) — this only spares the
 * user a round-trip on an obviously wrong file.
 */
const ACCEPTED = ['.jsonl', '.ndjson', '.csv', '.parquet'] as const

export interface FileDropzoneProps {
  onFileSelected: (file: File) => void
  disabled?: boolean
  busy?: boolean
}

export function FileDropzone({ onFileSelected, disabled = false, busy = false }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  function accept(file: File | undefined) {
    if (!file) return
    const name = file.name.toLowerCase()
    if (!ACCEPTED.some((extension) => name.endsWith(extension))) {
      setLocalError(`Unsupported extension. Expected one of ${ACCEPTED.join(', ')}.`)
      return
    }
    setLocalError(null)
    onFileSelected(file)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    accept(event.dataTransfer.files?.[0])
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    accept(event.target.files?.[0])
    // Let the same file be picked twice in a row (after a failed upload).
    event.target.value = ''
  }

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        className={cn(
          'glass-surface flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-12 text-center transition-colors',
          dragging && 'border-primary bg-primary-soft',
          disabled && 'opacity-50',
        )}
      >
        <UploadCloud className="size-8 text-foreground-subtle" aria-hidden />
        <p className="mt-4 text-body text-foreground">Drop a trace file here</p>
        <p className="mt-1 text-secondary text-foreground-muted">
          JSONL, CSV or Parquet — the format is detected server-side.
        </p>
        <Button
          type="button"
          variant="secondary"
          className="mt-6"
          disabled={disabled}
          loading={busy}
          onClick={() => inputRef.current?.click()}
        >
          Choose a file
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(',')}
          className="sr-only"
          onChange={handleChange}
          disabled={disabled}
        />
      </div>
      {localError ? (
        <p role="alert" className="mt-3 text-secondary text-error">
          {localError}
        </p>
      ) : null}
    </div>
  )
}
