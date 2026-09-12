import { Badge, type BadgeVariant } from '@woobe/ui'
import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  size?: 'default' | 'compact'
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
    <Badge
      variant={variant}
      className={cn(
        'font-mono uppercase tracking-[0.06em]',
        size === 'compact' && 'px-1.5 py-0.5 text-[8px]',
        className,
      )}
    >
      {status}
    </Badge>
  )
}
