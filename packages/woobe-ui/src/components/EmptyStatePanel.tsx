import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export type EmptyStatePanelVariant = 'default' | 'plain' | 'error'

const variantClasses: Record<EmptyStatePanelVariant, string> = {
  default: 'border-dashed border-border bg-background/20',
  plain: 'border-transparent bg-transparent',
  error: 'border-solid border-error/25 bg-error/[0.04]',
}

export interface EmptyStatePanelProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  icon?: ReactNode
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  compact?: boolean
  variant?: EmptyStatePanelVariant
}

const EmptyStatePanel = forwardRef<HTMLDivElement, EmptyStatePanelProps>(
  ({ className, icon, title, description, action, compact = false, variant = 'default', ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex flex-col items-center justify-center rounded-container border text-center',
        variantClasses[variant],
        compact ? 'min-h-24 px-ui-lg py-ui-md' : 'min-h-48 px-ui-xxl py-ui-xxl',
        className,
      )}
      {...props}
    >
      {icon ? <div className="mb-ui-lg flex h-control-row w-control-row items-center justify-center rounded-container border border-border bg-control text-primary">{icon}</div> : null}
      <div className="font-sans text-section-title font-medium text-slate-200">{title}</div>
      {description ? (
        <div className={cn(
          'mt-ui-xs max-w-md font-sans text-muted-foreground',
          'text-product-caption',
        )}>
          {description}
        </div>
      ) : null}
      {action ? <div className="mt-ui-md">{action}</div> : null}
    </div>
  ),
)
EmptyStatePanel.displayName = 'EmptyStatePanel'

export { EmptyStatePanel }
