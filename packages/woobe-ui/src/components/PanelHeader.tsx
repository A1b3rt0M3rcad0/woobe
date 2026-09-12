import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface PanelHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title: ReactNode
  description?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  compact?: boolean
}

export function PanelHeader({
  title,
  description,
  icon,
  actions,
  compact = false,
  className,
  ...props
}: PanelHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-ui-md border-b border-border',
        compact ? 'px-ui-md py-ui-sm' : 'px-ui-md py-ui-md',
        className,
      )}
      {...props}
    >
      <div className="flex min-w-0 items-start gap-ui-sm">
        {icon ? (
          <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <div className="font-mono text-system-label font-bold text-slate-50">{title}</div>
          {description ? <div className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{description}</div> : null}
        </div>
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}
