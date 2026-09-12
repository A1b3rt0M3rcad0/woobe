import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface PageHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
  compact?: boolean
}

const PageHeader = forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ className, title, description, actions, eyebrow, compact = false, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'mb-ui-xl flex flex-col gap-ui-md border-b border-border',
        compact ? 'pb-ui-md' : 'pb-ui-lg',
        'sm:flex-row sm:items-end sm:justify-between',
        className,
      )}
      {...props}
    >
      <div className="min-w-0">
        {eyebrow ? (
          <div className="mb-ui-xs font-mono text-system-label uppercase tracking-system text-primary-light">
            {eyebrow}
          </div>
        ) : null}
        <h1 className="font-mono text-[15px] font-semibold leading-5 tracking-[-0.01em] text-slate-100">
          {title}
        </h1>
        {description ? (
          <div className="mt-ui-xs max-w-3xl font-sans text-product-caption leading-5 text-muted-foreground">
            {description}
          </div>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-ui-sm">{actions}</div> : null}
    </div>
  ),
)
PageHeader.displayName = 'PageHeader'

export { PageHeader }
