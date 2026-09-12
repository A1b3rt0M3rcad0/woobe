import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface SectionBlockProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
  density?: 'compact' | 'default'
}

const SectionBlock = forwardRef<HTMLElement, SectionBlockProps>(
  ({ className, title, description, actions, eyebrow, density = 'default', children, ...props }, ref) => {
    const hasChildren = children !== null && children !== undefined && children !== false
    const spacing = density === 'compact' ? 'p-ui-md' : 'p-ui-lg'
    const contentGap = hasChildren ? (density === 'compact' ? 'mb-ui-md' : 'mb-ui-lg') : undefined

    return (
      <section ref={ref} className={cn('rounded-container border border-border bg-surface/70', spacing, className)} {...props}>
        {(title || description || actions || eyebrow) ? (
          <div className={cn('flex items-start justify-between gap-ui-md', contentGap)}>
            <div className="min-w-0">
              {eyebrow ? <div className="mb-ui-xs font-mono text-system-meta uppercase tracking-ui-eyebrow text-muted-foreground">{eyebrow}</div> : null}
              {title ? <div className="font-mono text-system-control font-semibold text-accent-foreground">{title}</div> : null}
              {description ? <div className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{description}</div> : null}
            </div>
            {actions ? <div className="shrink-0">{actions}</div> : null}
          </div>
        ) : null}
        {children}
      </section>
    )
  },
)
SectionBlock.displayName = 'SectionBlock'

export { SectionBlock }
