import { type ReactNode } from 'react'
import { ArrowRight, CheckCircle2, Inbox } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

interface GuidedEmptyStateProps {
  icon?: ReactNode
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  secondaryAction?: ReactNode
  next?: string[]
  className?: string
}

export function GuidedEmptyState({ icon, title, description, actionLabel, onAction, secondaryAction, next, className }: GuidedEmptyStateProps) {
  return (
    <div className={cn('rounded-2xl border border-dashed border-border bg-surface/60 p-8 text-center', className)}>
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-background text-primary-light">
        {icon || <Inbox className="h-6 w-6" />}
      </div>
      <h3 className="mt-4 text-lg font-semibold text-white">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm text-muted">{description}</p>
      {next && next.length > 0 && (
        <div className="mx-auto mt-5 grid max-w-2xl gap-2 text-left sm:grid-cols-3">
          {next.map((item) => (
            <div key={item} className="flex items-start gap-2 rounded-xl border border-border bg-background/70 p-3 text-xs text-muted">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-light" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      )}
      {(actionLabel || secondaryAction) && (
        <div className="mt-6 flex flex-col items-center justify-center gap-2 sm:flex-row">
          {actionLabel && onAction && (
            <Button onClick={onAction}>
              {actionLabel}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          )}
          {secondaryAction}
        </div>
      )}
    </div>
  )
}
