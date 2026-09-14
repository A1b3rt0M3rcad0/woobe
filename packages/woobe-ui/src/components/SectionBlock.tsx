import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface SectionBlockProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
  density?: 'compact' | 'default'
  variant?: 'technical' | 'product'
  hierarchy?: 'primary' | 'secondary'
}

const SectionBlock = forwardRef<HTMLElement, SectionBlockProps>(
  ({
    className,
    title,
    description,
    actions,
    eyebrow,
    density = 'default',
    variant = 'technical',
    hierarchy = 'primary',
    children,
    ...props
  }, ref) => {
    const hasChildren = children !== null && children !== undefined && children !== false
    const product = variant === 'product'
    const secondary = hierarchy === 'secondary'
    const spacing = density === 'compact' ? 'p-ui-md' : 'p-ui-panel-inset'
    const contentGap = hasChildren ? (density === 'compact' || secondary ? 'mb-ui-sm' : 'mb-ui-md') : undefined
    const titleClass = secondary ? 'text-system-control' : 'text-section-title'
    const descriptionClass = 'text-system-meta'
    const familyClass = product ? 'font-sans' : 'font-mono'

    return (
      <section ref={ref} className={cn('rounded-container border border-border bg-surface/70', spacing, className)} {...props}>
        {(title || description || actions || eyebrow) ? (
          <div className={cn('flex items-start justify-between gap-ui-md', contentGap)}>
            <div className="min-w-0">
              {eyebrow ? <div className="mb-ui-xs font-mono text-system-meta uppercase tracking-ui-eyebrow text-muted-foreground">{eyebrow}</div> : null}
              {title ? (
                <div className={cn(
                  'font-semibold text-accent-foreground',
                  titleClass,
                  familyClass,
                )}>
                  {title}
                </div>
              ) : null}
              {description ? (
                <div className={cn('mt-ui-xs text-muted-foreground', descriptionClass, familyClass)}>
                  {description}
                </div>
              ) : null}
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
