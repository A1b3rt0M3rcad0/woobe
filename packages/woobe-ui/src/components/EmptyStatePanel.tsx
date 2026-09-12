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
        compact ? 'min-h-[92px] px-4 py-4' : 'min-h-[132px] px-5 py-5',
        className,
      )}
      {...props}
    >
      {icon ? <div className="mb-2 text-muted-foreground">{icon}</div> : null}
      <div className="font-mono text-[9px] font-semibold leading-4 text-slate-200">{title}</div>
      {description ? <div className="mt-1 max-w-md font-sans text-[9px] leading-4 text-muted-foreground">{description}</div> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  ),
)
EmptyStatePanel.displayName = 'EmptyStatePanel'

export { EmptyStatePanel }
