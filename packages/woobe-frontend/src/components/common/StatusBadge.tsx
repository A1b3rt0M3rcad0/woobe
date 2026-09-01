import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  size?: 'default' | 'compact'
  className?: string
}

const statusMap: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
  active: 'success',
  inactive: 'secondary',
  pending: 'warning',
  failed: 'destructive',
  error: 'destructive',
  indexed: 'success',
  parsing: 'warning',
  embedding: 'warning',
  queued: 'secondary',
  uploaded: 'default',
  read_only: 'default',
  write: 'warning',
  destructive: 'destructive',
  restricted: 'destructive',
  deleted: 'destructive',
}

export function StatusBadge({ status, size = 'default', className }: StatusBadgeProps) {
  const variant = statusMap[status.toLowerCase()] || 'default'
  return (
    <Badge
      variant={variant}
      className={cn(size === 'compact' && 'rounded-full px-2 py-0.5 text-[10px] font-medium', className)}
    >
      {status}
    </Badge>
  )
}
