import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'link'
export type ButtonSize = 'default' | 'sm' | 'lg' | 'icon'

const variantClasses: Record<ButtonVariant, string> = {
  default: 'border border-primary bg-primary text-white hover:border-primary-hover hover:bg-primary-hover',
  secondary: 'border border-border bg-accent text-accent-foreground hover:bg-border',
  outline: 'border border-border bg-transparent text-slate-200 hover:bg-accent hover:text-accent-foreground',
  ghost: 'border border-transparent bg-transparent text-slate-300 hover:bg-accent hover:text-accent-foreground',
  destructive: 'border border-red-600 bg-red-600 text-white hover:border-red-700 hover:bg-red-700',
  link: 'border border-transparent bg-transparent p-0 text-primary-light underline-offset-4 hover:underline',
}

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-9 px-4 py-2',
  sm: 'h-8 px-3 text-xs',
  lg: 'h-10 px-5',
  icon: 'h-9 w-9 p-0',
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
        'inline-flex items-center justify-center whitespace-nowrap rounded-control text-sm font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
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
          className="mr-2 h-3.5 w-3.5 animate-spin rounded-full border border-current border-r-transparent"
        />
      )}
      {children}
    </button>
  ),
)

Button.displayName = 'Button'

export { Button }
