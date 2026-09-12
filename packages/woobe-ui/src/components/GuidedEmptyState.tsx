import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { ArrowRight, CheckCircle2, Inbox } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from './Button'

export interface GuidedEmptyStateProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  icon?: ReactNode
  title: ReactNode
  description: ReactNode
  actionLabel?: string
  onAction?: () => void
  secondaryAction?: ReactNode
  next?: ReactNode[]
}

const GuidedEmptyState = forwardRef<HTMLDivElement, GuidedEmptyStateProps>(
  ({ icon, title, description, actionLabel, onAction, secondaryAction, next, className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('rounded-container border border-dashed border-border bg-background/20 p-ui-xl text-center', className)}
      {...props}
    >
      <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-primary-light">
        {icon || <Inbox className="h-4 w-4" />}
      </div>
      <div className="mt-ui-md font-mono text-system-heading font-semibold text-slate-100">{title}</div>
      <div className="mx-auto mt-ui-xs max-w-xl font-sans text-product-caption leading-5 text-muted-foreground">{description}</div>
      {next && next.length > 0 ? (
        <div className="mx-auto mt-ui-lg grid max-w-2xl gap-px overflow-hidden rounded-container border border-border bg-border text-left sm:grid-cols-3">
          {next.map((item, index) => (
            <div key={index} className="flex min-h-12 items-start gap-ui-sm bg-control/90 p-ui-md">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-light" />
              <span className="font-sans text-product-caption leading-4 text-muted-foreground">{item}</span>
            </div>
          ))}
        </div>
      ) : null}
      {actionLabel || secondaryAction ? (
        <div className="mt-ui-lg flex flex-col items-center justify-center gap-ui-sm sm:flex-row">
          {actionLabel && onAction ? (
            <Button onClick={onAction}>
              {actionLabel}
              <ArrowRight className="ml-ui-xs h-3.5 w-3.5" />
            </Button>
          ) : null}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  ),
)
GuidedEmptyState.displayName = 'GuidedEmptyState'

export { GuidedEmptyState }
