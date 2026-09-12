import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface SectionBlockProps extends HTMLAttributes<HTMLElement> {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
  density?: 'compact' | 'default'
}

const SectionBlock = forwardRef<HTMLElement, SectionBlockProps>(
  ({ className, title, description, actions, eyebrow, density = 'default', children, ...props }, ref) => (
    <section
      ref={ref}
      className={cn(
        'rounded-container border border-border bg-surface/70',
        density === 'compact' ? 'p-3' : 'p-4',
        className,
      )}
      {...props}
    >
      {(title || description || actions || eyebrow) ? (
        <div className={cn('flex items-start justify-between gap-3', children && (density === 'compact' ? 'mb-3' : 'mb-4'))}>
          <div className="min-w-0">
            {eyebrow ? <div className="mb-1 font-mono text-[8px] uppercase tracking-[0.12em] text-muted-foreground">{eyebrow}</div> : null}
            {title ? <div className="font-mono text-[10px] font-semibold leading-4 text-slate-50">{title}</div> : null}
            {description ? <div className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{description}</div> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  ),
)
SectionBlock.displayName = 'SectionBlock'

export { SectionBlock }
