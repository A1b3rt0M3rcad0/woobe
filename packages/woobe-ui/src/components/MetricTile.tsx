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
      className={cn('woobe-metric-tile min-w-0 rounded-container border border-border bg-surface shadow-panel px-ui-xl py-ui-lg', className)}
      {...props}
    >
      <div className="flex items-center gap-ui-xs font-sans text-chrome-label text-muted-foreground">
        {icon ? <span className="shrink-0 text-muted-foreground">{icon}</span> : null}
        <span>{label}</span>
      </div>
      <div className="woobe-metric-value mt-ui-sm whitespace-nowrap font-mono text-metric tabular-nums font-normal text-accent-foreground">{value}</div>
      {detail ? <div className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{detail}</div> : null}
    </div>
  ),
)
MetricTile.displayName = 'MetricTile'

export { MetricTile }
