import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: ReactNode
  icon?: ReactNode
  className?: string
}

export function MetricCard({ label, value, icon, className }: MetricCardProps) {
  return (
    <div className={cn('rounded-lg border border-border bg-background p-3', className)}>
      <div className="flex items-center gap-2">
        {icon && <span className="text-muted shrink-0">{icon}</span>}
        <p className="text-xs text-muted">{label}</p>
      </div>
      <p className="text-sm font-medium text-white mt-1">{value}</p>
    </div>
  )
}
