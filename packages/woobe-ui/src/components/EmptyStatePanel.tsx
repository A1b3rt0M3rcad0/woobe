import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface EmptyStatePanelProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  icon?: ReactNode
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  compact?: boolean
}

const EmptyStatePanel = forwardRef<HTMLDivElement, EmptyStatePanelProps>(
  ({ className, icon, title, description, action, compact = false, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex flex-col items-center justify-center rounded-container border border-dashed border-border bg-background/20 text-center',
        compact ? 'min-h-24 px-ui-lg py-ui-md' : 'min-h-32 px-ui-xl py-ui-lg',
        className,
      )}
      {...props}
    >
      {icon ? <div className="mb-ui-sm text-muted-foreground">{icon}</div> : null}
      <div className="font-mono text-system-control font-semibold text-slate-200">{title}</div>
      {description ? <div className="mt-ui-xs max-w-md font-sans text-product-caption text-muted-foreground">{description}</div> : null}
      {action ? <div className="mt-ui-md">{action}</div> : null}
    </div>
  ),
)
EmptyStatePanel.displayName = 'EmptyStatePanel'

export { EmptyStatePanel }