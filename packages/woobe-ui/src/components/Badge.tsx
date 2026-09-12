import { type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type BadgeVariant = 'default' | 'outline' | 'success' | 'warning' | 'destructive' | 'network'

const variantClasses: Record<BadgeVariant, string> = {
  default: 'border-primary/30 bg-primary/[0.08] text-primary-light',
  outline: 'border-border bg-background/50 text-muted-foreground',
  success: 'border-success/30 bg-success/[0.08] text-success',
  warning: 'border-warning/30 bg-warning/[0.08] text-warning',
  destructive: 'border-error/25 bg-error/[0.06] text-error',
  network: 'border-network/30 bg-network/[0.08] text-network',
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
