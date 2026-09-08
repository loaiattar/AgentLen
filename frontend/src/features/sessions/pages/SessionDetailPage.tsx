import { getRouteApi } from '@tanstack/react-router'

const routeApi = getRouteApi('/_app/sessions/$sessionId')

export function SessionDetailPage() {
  const { sessionId } = routeApi.useParams()
  return <div className="p-4">Session {sessionId}</div>
}
