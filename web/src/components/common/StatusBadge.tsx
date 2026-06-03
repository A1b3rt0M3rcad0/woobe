import { Badge } from '@/components/ui/Badge'

interface StatusBadgeProps {
  status: string
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

export function StatusBadge({ status }: StatusBadgeProps) {
  const variant = statusMap[status.toLowerCase()] || 'default'
  return <Badge variant={variant}>{status}</Badge>
}
