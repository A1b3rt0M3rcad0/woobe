import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface MetricTileProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode
  value: ReactNode
  icon?: ReactNode
  detail?: ReactNode
}

const MetricTile = forwardRef<HTMLDivElement, MetricTileProps>(
  ({ className, label, value, icon, detail, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('min-w-0 rounded-container border border-border bg-background/35 px-ui-lg py-ui-sm', className)}
      {...props}
    >
      <div className="flex items-center gap-ui-xs font-mono text-system-meta uppercase tracking-[0.08em] text-muted-foreground">
        {icon ? <span className="shrink-0 text-muted-foreground">{icon}</span> : null}
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-ui-xs truncate font-mono text-product-small font-semibold text-slate-50">{value}</div>
      {detail ? <div className="mt-ui-xs truncate font-sans text-product-caption text-muted-foreground">{detail}</div> : null}
    </div>
  ),
)
MetricTile.displayName = 'MetricTile'

export { MetricTile }
