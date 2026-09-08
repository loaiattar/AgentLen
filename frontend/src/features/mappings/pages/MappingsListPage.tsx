import { DataTable, type DataTableColumn } from '@/components/organisms/DataTable'
import { useMappingsQuery } from '@/features/mappings/api/mappings.queries'
import { formatDate } from '@/lib/utils/formatDate'
import type { Mapping } from '@/features/mappings/types'

const columns: DataTableColumn<Mapping>[] = [
  { header: 'Nom', cell: (row) => row.name },
  { header: 'Champs', cell: (row) => row.fields.length },
  { header: 'Créé le', cell: (row) => formatDate(row.createdAt) },
]

export function MappingsListPage() {
  const { data, isLoading, isError } = useMappingsQuery()

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">Mappings</h1>
      <DataTable columns={columns} data={data} isLoading={isLoading} isError={isError} getRowId={(row) => row.id} />
    </div>
  )
}
