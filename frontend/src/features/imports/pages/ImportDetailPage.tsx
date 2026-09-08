import { getRouteApi } from '@tanstack/react-router'

const routeApi = getRouteApi('/_app/imports/$importId')

export function ImportDetailPage() {
  const { importId } = routeApi.useParams()
  return <div className="p-4">Import {importId}</div>
}
