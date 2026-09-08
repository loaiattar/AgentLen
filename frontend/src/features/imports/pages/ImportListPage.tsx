import { useRef } from 'react'
import { Link } from '@tanstack/react-router'

import { Button } from '@/components/atoms/Button'
import { DataTable, type DataTableColumn } from '@/components/organisms/DataTable'
import { useImportsQuery } from '@/features/imports/api/imports.queries'
import { useCreateImportMutation } from '@/features/imports/api/imports.mutations'
import { ImportStatusBadge } from '@/features/imports/components/ImportStatusBadge'
import { formatDate } from '@/lib/utils/formatDate'
import type { ImportItem } from '@/features/imports/types'

const columns: DataTableColumn<ImportItem>[] = [
  {
    header: 'Fichier',
    cell: (row) => (
      <Link to="/imports/$importId" params={{ importId: row.id }} className="font-medium hover:underline">
        {row.fileName}
      </Link>
    ),
  },
  { header: 'Statut', cell: (row) => <ImportStatusBadge status={row.status} /> },
  { header: 'Lignes', cell: (row) => row.rowCount },
  { header: 'Créé le', cell: (row) => formatDate(row.createdAt) },
]

export function ImportListPage() {
  const { data, isLoading, isError } = useImportsQuery()
  const createImport = useCreateImportMutation()
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Imports</h1>
        <Button onClick={() => fileInputRef.current?.click()} disabled={createImport.isPending}>
          {createImport.isPending ? 'Envoi…' : 'Importer un fichier'}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) createImport.mutate(file)
            event.target.value = ''
          }}
        />
      </div>

      <DataTable columns={columns} data={data} isLoading={isLoading} isError={isError} getRowId={(row) => row.id} />
    </div>
  )
}
