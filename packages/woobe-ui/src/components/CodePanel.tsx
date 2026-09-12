import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface CodePanelProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode
  icon?: ReactNode
  badge?: ReactNode
  actions?: ReactNode
  density?: 'compact' | 'default'
}

const CodePanel = forwardRef<HTMLDivElement, CodePanelProps>(
  ({ className, title, icon, badge, actions, density = 'default', children, ...props }, ref) => (
    <div ref={ref} className={cn('overflow-hidden rounded-container border border-border bg-background/30', className)} {...props}>
      <div className={cn('flex items-center justify-between gap-ui-md border-b border-border bg-control/25', density === 'compact' ? 'min-h-control px-ui-lg' : 'min-h-control-row px-ui-md')}>
        <div className="flex min-w-0 items-center gap-ui-sm">
          {icon ? <span className="shrink-0 text-primary-light">{icon}</span> : null}
          <span className="truncate font-mono text-system-label font-semibold text-slate-100">{title}</span>
          {badge ? <span className="shrink-0 rounded-technical border border-primary/25 bg-primary/[0.08] px-ui-xs py-ui-hairline font-mono text-system-meta uppercase tracking-[0.08em] text-primary-light">{badge}</span> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-ui-xs">{actions}</div> : null}
      </div>
      {children}
    </div>
  ),
)
CodePanel.displayName = 'CodePanel'

export { CodePanel }
