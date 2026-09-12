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
      className={cn('min-w-0 rounded-container border border-border bg-background/35 px-2.5 py-2', className)}
      {...props}
    >
      <div className="flex items-center gap-1.5 font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">
        {icon ? <span className="shrink-0 text-muted-foreground">{icon}</span> : null}
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-1 truncate font-mono text-[11px] font-semibold leading-4 text-slate-50">{value}</div>
      {detail ? <div className="mt-0.5 truncate font-sans text-[8px] leading-3.5 text-muted-foreground">{detail}</div> : null}
    </div>
  ),
)
MetricTile.displayName = 'MetricTile'

export { MetricTile }
