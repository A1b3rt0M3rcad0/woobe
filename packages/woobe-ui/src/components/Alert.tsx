import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type AlertVariant = 'default' | 'info' | 'success' | 'warning' | 'destructive'

const variantClasses: Record<AlertVariant, string> = {
  default: 'border-border bg-surface text-slate-200',
  info: 'border-primary/30 bg-primary/[0.07] text-primary-light',
  success: 'border-emerald-500/30 bg-emerald-500/[0.07] text-emerald-300',
  warning: 'border-amber-500/30 bg-amber-500/[0.07] text-amber-300',
  destructive: 'border-red-500/25 bg-control/80 text-red-200',
}

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant
}

const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'default', ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn(
        'relative w-full rounded-container border px-3 py-2.5 text-xs leading-5',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  ),
)
Alert.displayName = 'Alert'

const AlertTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h5 ref={ref} className={cn('mb-1 font-mono text-[10px] font-medium leading-none', className)} {...props} />
  ),
)
AlertTitle.displayName = 'AlertTitle'

const AlertDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-sans opacity-90', className)} {...props} />
  ),
)
AlertDescription.displayName = 'AlertDescription'

export { Alert, AlertTitle, AlertDescription }
