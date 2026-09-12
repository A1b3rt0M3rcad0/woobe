import { Badge, type BadgeSize, type BadgeVariant } from '@woobe/ui'
import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  size?: BadgeSize
  className?: string
}

const statusMap: Record<string, BadgeVariant> = {
  active: 'success',
  inactive: 'outline',
  pending: 'warning',
  failed: 'destructive',
  error: 'destructive',
  indexed: 'success',
  parsing: 'warning',
  embedding: 'warning',
  queued: 'outline',
  uploaded: 'default',
  read_only: 'default',
  write: 'warning',
  destructive: 'destructive',
  restricted: 'destructive',
  deleted: 'destructive',
  archived: 'outline',
  deprecated: 'outline',
  revoked: 'destructive',
}

export function StatusBadge({ status, size = 'default', className }: StatusBadgeProps) {
  const variant = statusMap[status.toLowerCase()] || 'default'
  return (
    <Badge variant={variant} size={size} className={cn('uppercase tracking-ui-label', className)}>
      {status}
    </Badge>
  )
}
