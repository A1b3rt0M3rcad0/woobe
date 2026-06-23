import { type ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { cn } from '@/lib/utils'

interface ResourceCardProps {
  icon?: ReactNode
  title: ReactNode
  description?: ReactNode
  badge?: ReactNode
  metadata?: ReactNode
  actions?: ReactNode
  selected?: boolean
  className?: string
}

export function ResourceCard({ icon, title, description, badge, metadata, actions, selected, className }: ResourceCardProps) {
  return (
    <Card className={cn('group relative overflow-hidden transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5', selected ? 'border-primary/60 bg-primary/10 ring-1 ring-primary/30' : 'border-border bg-surface', className)}>
      <CardHeader className="pb-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          {icon && <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm">{icon}</div>}
          {badge}
        </div>
        <CardTitle className="text-white">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {metadata}
        {actions && <div className="flex flex-col gap-2 sm:flex-row">{actions}</div>}
      </CardContent>
    </Card>
  )
}
