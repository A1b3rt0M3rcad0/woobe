import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Badge, type BadgeVariant } from './Badge'
import { cn } from '../lib/cn'

export interface ResourceCardProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'title'> {
  icon: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  description?: ReactNode
  status?: ReactNode
  metadata?: ReactNode
  footer?: ReactNode
  showChevron?: boolean
}

export function ResourceCard({
  icon,
  title,
  subtitle,
  description,
  status,
  metadata,
  footer,
  showChevron = true,
  className,
  type = 'button',
  ...props
}: ResourceCardProps) {
  return (
    <button
      type={type}
      className={cn(
        'group flex min-h-resource-card w-full flex-col overflow-hidden rounded-container border border-border bg-surface shadow-panel text-left transition-colors',
        'hover:border-muted hover:bg-surface focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <span className="flex items-start justify-between gap-ui-md px-ui-panel-inset py-ui-lg">
        <span className="flex min-w-0 items-start gap-ui-sm">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-[#ffe6d9] text-primary-light">{icon}</span>
          <span className="min-w-0 pt-ui-hairline">
            <span className="block break-words font-mono text-product-label font-medium text-accent-foreground">{title}</span>
            {subtitle ? <span className="mt-ui-xs block break-words font-sans text-product-caption text-muted-foreground">{subtitle}</span> : null}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-ui-xs">
          {status}
          {showChevron ? <ChevronRight className="h-icon w-icon text-muted-foreground transition-[color,transform] group-hover:translate-x-px group-hover:text-primary-light" aria-hidden="true" /> : null}
        </span>
      </span>

      {description ? <span className="block px-ui-panel-inset pb-ui-lg font-sans text-product-small text-muted-foreground">{description}</span> : null}
      {metadata ? <span className="flex flex-1 flex-wrap content-start items-start gap-ui-xs border-t border-border/70 px-ui-panel-inset py-ui-md">{metadata}</span> : null}
      {footer ? <span className="mt-auto block border-t border-border bg-panel-band/70 px-ui-panel-inset py-ui-md font-mono text-system-meta text-muted-foreground">{footer}</span> : null}
    </button>
  )
}

export type ResourcePillTone = 'default' | 'primary' | 'success' | 'warning' | 'danger'

const pillVariant: Record<ResourcePillTone, BadgeVariant> = {
  default: 'outline',
  primary: 'default',
  success: 'success',
  warning: 'warning',
  danger: 'destructive',
}

export function ResourcePill({ children, tone = 'default', className }: { children: ReactNode; tone?: ResourcePillTone; className?: string }) {
  return <Badge size="compact" variant={pillVariant[tone]} className={className}>{children}</Badge>
}
