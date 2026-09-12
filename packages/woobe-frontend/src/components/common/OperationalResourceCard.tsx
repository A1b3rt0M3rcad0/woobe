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
        'group flex min-h-[154px] w-full flex-col overflow-hidden rounded-container border border-border bg-surface/[0.94] text-left transition-colors',
        'hover:border-slate-600 hover:bg-surface',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary focus-visible:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <span className="flex items-start justify-between gap-3 px-3.5 py-3">
        <span className="flex min-w-0 items-start gap-2.5">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
            {icon}
          </span>
          <span className="min-w-0 pt-px">
            <span className="block truncate font-mono text-[11px] font-bold text-slate-50">{title}</span>
            {subtitle && <span className="mt-1 block truncate text-[10px] leading-4 text-muted-foreground">{subtitle}</span>}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          {status}
          {showChevron && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground transition-[color,transform] group-hover:translate-x-0.5 group-hover:text-primary-light" aria-hidden="true" />}
        </span>
      </span>

      {metadata && (
        <span className="flex flex-1 flex-wrap content-start items-start gap-1.5 border-t border-border/70 px-3.5 py-3">
          {metadata}
        </span>
      )}
      {footer && (
        <span className="mt-auto block border-t border-border/70 bg-control/35 px-3.5 py-2 font-mono text-[8px] leading-4 text-muted-foreground">
          {footer}
        </span>
      )}
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
    default: 'border-border bg-control/70 text-muted-foreground',
    primary: 'border-primary/30 bg-primary/[0.08] text-primary-light',
    success: 'border-emerald-500/25 bg-emerald-500/[0.07] text-emerald-300',
    warning: 'border-amber-500/25 bg-amber-500/[0.07] text-amber-200',
    danger: 'border-red-500/25 bg-red-500/[0.07] text-red-200',
  }[tone]

  return (
    <span className={cn('rounded-technical border px-2 py-1 font-mono text-[8px] font-medium leading-none', toneClass, className)}>
      {children}
    </span>
  )
}
