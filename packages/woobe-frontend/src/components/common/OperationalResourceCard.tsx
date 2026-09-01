import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'

import { cn } from '@/lib/utils'

interface ResourceCardProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'title'> {
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
        'group rounded-xl border border-border/90 bg-surface/70 p-4 text-left transition-colors',
        'hover:border-primary/35 hover:bg-surface/85',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <span className="flex items-start justify-between gap-4">
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            {icon}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-white">{title}</span>
            {subtitle && <span className="mt-1 block truncate text-[11px] text-muted">{subtitle}</span>}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {status}
          {showChevron && <ChevronRight className="h-4 w-4 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" aria-hidden="true" />}
        </span>
      </span>

      {metadata && <span className="mt-4 flex flex-wrap items-center gap-2">{metadata}</span>}
      {footer && <span className="mt-4 block text-[10px] text-muted">{footer}</span>}
    </button>
  )
}

export function ResourcePill({
  children,
  tone = 'default',
  className,
}: {
  children: ReactNode
  tone?: 'default' | 'primary' | 'success' | 'warning' | 'danger'
  className?: string
}) {
  const toneClass = {
    default: 'border-border/80 bg-background/55 text-muted',
    primary: 'border-primary/30 bg-primary/10 text-primary-light',
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
    danger: 'border-red-500/30 bg-red-500/10 text-red-200',
  }[tone]

  return <span className={cn('rounded-full border px-2.5 py-1 text-[10px] font-medium', toneClass, className)}>{children}</span>
}
