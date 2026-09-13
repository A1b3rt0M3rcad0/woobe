import { type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type BadgeVariant = 'default' | 'secondary' | 'outline' | 'success' | 'warning' | 'destructive' | 'network'
export type BadgeSize = 'compact' | 'default'

const variantClasses: Record<BadgeVariant, string> = {
  default: 'border-primary/30 bg-primary/[0.08] text-primary-light',
  secondary: 'border-border bg-accent/55 text-accent-foreground',
  outline: 'border-border bg-background/50 text-muted-foreground',
  success: 'border-success/30 bg-success/[0.08] text-success',
  warning: 'border-warning/30 bg-warning/[0.08] text-warning',
  destructive: 'border-error/25 bg-error/[0.06] text-error',
  network: 'border-network/30 bg-network/[0.08] text-network',
}

const sizeClasses: Record<BadgeSize, string> = {
  compact: 'gap-ui-hairline px-ui-xs py-ui-hairline text-system-meta',
  default: 'gap-ui-xs px-ui-sm py-ui-xs text-system-label',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
}

function Badge({ className, variant = 'default', size = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-technical border font-mono font-medium leading-none',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  )
}

export { Badge }
