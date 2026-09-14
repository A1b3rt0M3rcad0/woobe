import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'link'
export type ButtonSize = 'xs' | 'default' | 'sm' | 'lg' | 'icon' | 'iconSm' | 'iconXs'

const variantClasses: Record<ButtonVariant, string> = {
  default: 'border border-primary bg-primary font-medium text-accent-foreground hover:border-primary-hover hover:bg-primary-hover',
  secondary: 'border border-border bg-accent text-accent-foreground hover:bg-border',
  outline: 'border border-border bg-control text-accent-foreground/85 hover:border-muted hover:bg-accent hover:text-accent-foreground',
  ghost: 'border border-transparent bg-transparent text-accent-foreground/75 hover:bg-accent hover:text-accent-foreground',
  destructive: 'border border-error/40 bg-error/10 font-medium text-error hover:border-error/55 hover:bg-error/[0.16] hover:text-error',
  link: 'border border-transparent bg-transparent p-0 text-primary-light underline-offset-4 hover:underline',
}

const sizeClasses: Record<ButtonSize, string> = {
  xs: 'h-control-xs px-ui-sm text-chrome-meta',
  default: 'h-control px-ui-md text-chrome-control',
  sm: 'h-control-sm px-ui-sm text-chrome-label',
  lg: 'h-control-lg px-ui-lg text-chrome-control',
  icon: 'h-control w-control p-0',
  iconSm: 'h-control-sm w-control-sm p-0',
  iconXs: 'h-control-xs w-control-xs p-0',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', loading = false, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center gap-ui-sm whitespace-nowrap rounded-control font-mono transition-colors [&>svg]:!m-0 [&>svg]:shrink-0',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        'disabled:pointer-events-none disabled:opacity-50',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="h-icon-sm w-icon-sm animate-spin rounded-full border border-current border-r-transparent"
        />
      )}
      {children}
    </button>
  ),
)

Button.displayName = 'Button'

export { Button }
