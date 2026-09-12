import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'link'
export type ButtonSize = 'default' | 'sm' | 'lg' | 'icon'

const variantClasses: Record<ButtonVariant, string> = {
  default: 'border border-primary bg-primary text-white hover:border-primary-hover hover:bg-primary-hover',
  secondary: 'border border-border bg-accent text-accent-foreground hover:bg-border',
  outline: 'border border-border bg-control text-slate-200 hover:border-slate-600 hover:bg-[#13203a] hover:text-white',
  ghost: 'border border-transparent bg-transparent text-slate-300 hover:bg-accent hover:text-accent-foreground',
  destructive: 'border border-red-600 bg-red-600 text-white hover:border-red-700 hover:bg-red-700',
  link: 'border border-transparent bg-transparent p-0 text-primary-light underline-offset-4 hover:underline',
}

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-[34px] px-3',
  sm: 'h-[30px] px-2.5 text-[9px]',
  lg: 'h-[38px] px-4',
  icon: 'h-[34px] w-[34px] p-0',
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
        'inline-flex items-center justify-center whitespace-nowrap rounded-control font-mono text-[10px] font-medium transition-colors',
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
          className="mr-2 h-3 w-3 animate-spin rounded-full border border-current border-r-transparent"
        />
      )}
      {children}
    </button>
  ),
)

Button.displayName = 'Button'

export { Button }
