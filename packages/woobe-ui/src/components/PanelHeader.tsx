import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export type PanelHeaderHierarchy = 'technical' | 'section' | 'entity'

export interface PanelHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode
  description?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  compact?: boolean
  hierarchy?: PanelHeaderHierarchy
}

const titleClasses: Record<PanelHeaderHierarchy, string> = {
  technical: 'font-mono text-system-control font-semibold',
  section: 'font-mono text-section-title font-bold',
  entity: 'font-mono text-entity-title font-bold',
}

const descriptionClasses: Record<PanelHeaderHierarchy, string> = {
  technical: 'font-mono text-product-caption',
  section: 'font-mono text-product-caption',
  entity: 'font-mono text-system-control',
}

export function PanelHeader({
  title,
  description,
  icon,
  actions,
  compact = false,
  hierarchy = 'section',
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
          <div className={cn(titleClasses[hierarchy], 'text-accent-foreground')}>{title}</div>
          {description ? <div className={cn('mt-ui-xs text-muted-foreground', descriptionClasses[hierarchy])}>{description}</div> : null}
        </div>
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}
