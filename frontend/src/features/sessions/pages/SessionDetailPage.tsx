import { getRouteApi } from '@tanstack/react-router'

import { Badge } from '@/components/atoms/Badge'
import { useSessionDetailQuery } from '@/features/sessions/api/sessions.queries'
import { ModelCallsTable } from '@/features/sessions/components/ModelCallsTable'

const routeApi = getRouteApi('/_app/sessions/$sessionId')

export function SessionDetailPage() {
  const { sessionId } = routeApi.useParams()
  const { data, isLoading, isError } = useSessionDetailQuery(sessionId)

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold">Session {sessionId}</h1>
        {data && <Badge variant="secondary">{data.source}</Badge>}
      </div>

      {isError && <p className="text-sm text-destructive">Impossible de charger cette session.</p>}

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium text-muted-foreground">Appels modèles</h2>
        <ModelCallsTable data={data?.modelCalls} isLoading={isLoading} />
      </section>
    </div>
  )
}
