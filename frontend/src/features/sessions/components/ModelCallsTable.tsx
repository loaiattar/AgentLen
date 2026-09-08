import { DataTable, type DataTableColumn } from '@/components/organisms/DataTable'
import { formatDate } from '@/lib/utils/formatDate'
import type { ModelCall } from '@/features/sessions/types'

const columns: DataTableColumn<ModelCall>[] = [
  { header: 'Modèle', cell: (row) => row.model },
  { header: 'Démarré', cell: (row) => formatDate(row.startedAt) },
  { header: 'Latence', cell: (row) => `${row.latencyMs} ms` },
  { header: 'Tokens (in/out)', cell: (row) => `${row.tokensIn} / ${row.tokensOut}` },
]

export interface ModelCallsTableProps {
  data: ModelCall[] | undefined
  isLoading?: boolean
}

export function ModelCallsTable({ data, isLoading }: ModelCallsTableProps) {
  return <DataTable columns={columns} data={data} isLoading={isLoading} getRowId={(row) => row.id} />
}
