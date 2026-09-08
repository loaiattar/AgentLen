import type * as React from 'react'

export interface DataTableColumn<TRow> {
  header: string
  cell: (row: TRow) => React.ReactNode
  className?: string
}

export interface DataTableProps<TRow> {
  columns: DataTableColumn<TRow>[]
  data: TRow[] | undefined
  isLoading?: boolean
  isError?: boolean
  getRowId: (row: TRow) => string
  emptyMessage?: string
}

export function DataTable<TRow>({
  columns,
  data,
  isLoading,
  isError,
  getRowId,
  emptyMessage = 'Aucune donnée.',
}: DataTableProps<TRow>) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th key={column.header} className="px-3 py-2 font-medium">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {isLoading && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                Chargement…
              </td>
            </tr>
          )}
          {isError && !isLoading && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-destructive">
                Une erreur est survenue.
              </td>
            </tr>
          )}
          {!isLoading && !isError && data?.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          )}
          {!isLoading &&
            !isError &&
            data?.map((row) => (
              <tr key={getRowId(row)} className="hover:bg-muted/30">
                {columns.map((column) => (
                  <td key={column.header} className={column.className ?? 'px-3 py-2'}>
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  )
}
