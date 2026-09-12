import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface CodePanelProps extends HTMLAttributes<HTMLDivElement> {
  title: ReactNode
  icon?: ReactNode
  badge?: ReactNode
  actions?: ReactNode
  density?: 'compact' | 'default'
}

const CodePanel = forwardRef<HTMLDivElement, CodePanelProps>(
  ({ className, title, icon, badge, actions, density = 'default', children, ...props }, ref) => (
    <div ref={ref} className={cn('overflow-hidden rounded-container border border-border bg-background/30', className)} {...props}>
      <div className={cn('flex items-center justify-between gap-3 border-b border-border bg-control/25', density === 'compact' ? 'min-h-[34px] px-2.5' : 'min-h-[40px] px-3')}>
        <div className="flex min-w-0 items-center gap-2">
          {icon ? <span className="shrink-0 text-primary-light">{icon}</span> : null}
          <span className="truncate font-mono text-[9px] font-semibold text-slate-100">{title}</span>
          {badge ? <span className="shrink-0 rounded-technical border border-primary/25 bg-primary/[0.08] px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.08em] text-primary-light">{badge}</span> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </div>
      {children}
    </div>
  ),
)
CodePanel.displayName = 'CodePanel'

export { CodePanel }
