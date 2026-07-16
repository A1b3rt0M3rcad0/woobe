import { type ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { cn } from '@/lib/utils'

interface ResourceSummaryCardProps {
  label: string
  value: ReactNode
  detail?: ReactNode
  icon?: ReactNode
  className?: string
}

export function ResourceSummaryCard({ label, value, detail, icon, className }: ResourceSummaryCardProps) {
  return (
    <Card className={cn('border-border bg-surface/80', className)}>
      <CardContent className="flex items-start gap-3 p-4">
        {icon && <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary-light">{icon}</div>}
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
          {detail && <p className="mt-1 text-xs text-muted">{detail}</p>}
        </div>
      </CardContent>
    </Card>
  )
}
