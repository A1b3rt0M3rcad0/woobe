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
    <Card className={cn('group relative overflow-hidden transition-colors', selected ? 'border-primary/55 bg-primary/[0.06]' : 'border-border bg-surface', className)}>
      <CardHeader className="pb-3">
        <div className="mb-2 flex items-start justify-between gap-3">
          {icon ? <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">{icon}</div> : null}
          {badge}
        </div>
        <CardTitle className="font-mono text-[12px] font-semibold text-slate-100">{title}</CardTitle>
        {description ? <CardDescription className="font-sans text-xs leading-5 text-muted">{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {metadata}
        {actions ? <div className="flex flex-wrap gap-2 border-t border-border pt-3">{actions}</div> : null}
      </CardContent>
    </Card>
  )
}
