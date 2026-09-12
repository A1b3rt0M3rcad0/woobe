import { type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type BadgeVariant = 'default' | 'outline' | 'success' | 'warning' | 'destructive' | 'network'

const variantClasses: Record<BadgeVariant, string> = {
  default: 'border-primary/30 bg-primary/[0.08] text-primary-light',
  outline: 'border-border bg-background/50 text-muted-foreground',
  success: 'border-emerald-500/30 bg-emerald-500/[0.08] text-emerald-300',
  warning: 'border-amber-500/30 bg-amber-500/[0.08] text-amber-300',
  destructive: 'border-red-500/25 bg-red-500/[0.06] text-red-300',
  network: 'border-violet-500/30 bg-violet-500/[0.08] text-violet-300',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-ui-xs rounded-technical border px-ui-sm py-ui-xs font-mono text-system-label font-medium leading-none',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  )
}

export { Badge }
