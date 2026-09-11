import { getRouteApi, Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'

const routeApi = getRouteApi('/_app/imports/$importId')

export function ImportDetailPage() {
  const { importId } = routeApi.useParams()

  return (
    <div>
      <PageHeader
        kicker="Import"
        title={importId}
        action={
          <Button variant="secondary" asChild>
            <Link to="/imports" search={(prev) => prev}>
              Back
            </Link>
          </Button>
        }
      />
      <BentoGrid>
        <BentoModule cols={2} padding="none">
          <Kpi label="Records" value="12,440" />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Mapped fields" value="18" />
        </BentoModule>
        <BentoModule cols={1}>
          <p className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">Status</p>
          <div className="mt-6">
            <Badge tone="mint">completed</Badge>
          </div>
        </BentoModule>
        <BentoModule cols={1}>
          <p className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">Source</p>
          <p className="mt-6 text-body text-foreground">TraceLab</p>
        </BentoModule>
      </BentoGrid>
    </div>
  )
}
