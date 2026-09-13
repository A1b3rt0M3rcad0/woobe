import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Badge, type BadgeVariant } from './Badge'
import { cn } from '../lib/cn'

export interface ResourceCardProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'title'> {
  icon: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  status?: ReactNode
  metadata?: ReactNode
  footer?: ReactNode
  showChevron?: boolean
}

export function ResourceCard({
  icon,
  title,
  subtitle,
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
        'group flex min-h-[9.625rem] w-full flex-col overflow-hidden rounded-container border border-border bg-surface/[0.94] text-left transition-colors',
        'hover:border-muted hover:bg-surface focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <span className="flex items-start justify-between gap-ui-md px-ui-md py-ui-md">
        <span className="flex min-w-0 items-start gap-ui-sm">
          <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">{icon}</span>
          <span className="min-w-0 pt-ui-hairline">
            <span className="block truncate font-mono text-system-control font-bold text-accent-foreground">{title}</span>
            {subtitle ? <span className="mt-ui-xs block truncate font-mono text-system-label text-muted-foreground">{subtitle}</span> : null}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-ui-xs">
          {status}
          {showChevron ? <ChevronRight className="h-icon w-icon text-muted-foreground transition-[color,transform] group-hover:translate-x-px group-hover:text-primary-light" aria-hidden="true" /> : null}
        </span>
      </span>

      {metadata ? <span className="flex flex-1 flex-wrap content-start items-start gap-ui-xs border-t border-border/70 px-ui-md py-ui-md">{metadata}</span> : null}
      {footer ? <span className="mt-auto block border-t border-border/70 bg-control/35 px-ui-md py-ui-sm font-mono text-system-meta text-muted-foreground">{footer}</span> : null}
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
