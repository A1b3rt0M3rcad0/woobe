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
      <div className="mx-auto flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
        {icon || <Inbox className="h-icon-lg w-icon-lg" />}
      </div>
      <div className="mt-ui-md font-sans text-product-label font-semibold text-slate-100">{title}</div>
      <div className="mx-auto mt-ui-xs max-w-xl font-sans text-product-small text-muted-foreground">{description}</div>
      {next && next.length > 0 ? (
        <div className="mx-auto mt-ui-lg grid max-w-2xl gap-px overflow-hidden rounded-container border border-border bg-border text-left sm:grid-cols-3">
          {next.map((item, index) => (
            <div key={index} className="flex min-h-12 items-start gap-ui-sm bg-control/90 p-ui-md">
              <CheckCircle2 className="mt-ui-hairline h-icon w-icon shrink-0 text-primary-light" />
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
              <ArrowRight className="ml-ui-xs h-icon w-icon" />
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