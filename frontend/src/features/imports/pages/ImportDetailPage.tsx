import { getRouteApi } from '@tanstack/react-router'

import { useImportQuery } from '@/features/imports/api/imports.queries'
import { ImportStatusBadge } from '@/features/imports/components/ImportStatusBadge'
import { formatDate } from '@/lib/utils/formatDate'

const routeApi = getRouteApi('/_app/imports/$importId')

export function ImportDetailPage() {
  const { importId } = routeApi.useParams()
  const { data, isLoading, isError } = useImportQuery(importId)

  if (isLoading) return <p className="p-4 text-muted-foreground">Chargement…</p>
  if (isError || !data) return <p className="p-4 text-destructive">Import introuvable.</p>

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold">{data.fileName}</h1>
        <ImportStatusBadge status={data.status} />
      </div>
      <dl className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <dt className="text-muted-foreground">Lignes</dt>
          <dd>{data.rowCount}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Créé le</dt>
          <dd>{formatDate(data.createdAt)}</dd>
        </div>
      </dl>
    </div>
  )
}
