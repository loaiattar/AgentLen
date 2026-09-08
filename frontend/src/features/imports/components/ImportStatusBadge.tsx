import { Badge } from '@/components/atoms/Badge'
import type { ImportStatus } from '@/features/imports/types'

const STATUS_LABEL: Record<ImportStatus, string> = {
  pending: 'En attente',
  processing: 'En cours',
  completed: 'Terminé',
  failed: 'Échoué',
}

const STATUS_VARIANT: Record<ImportStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'outline',
  processing: 'secondary',
  completed: 'default',
  failed: 'destructive',
}

export function ImportStatusBadge({ status }: { status: ImportStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>
}
