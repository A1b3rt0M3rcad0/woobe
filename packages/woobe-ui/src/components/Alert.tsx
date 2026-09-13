import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type AlertVariant = 'default' | 'info' | 'success' | 'warning' | 'destructive'

const variantClasses: Record<AlertVariant, string> = {
  default: 'border-border bg-surface text-accent-foreground/85',
  info: 'border-primary/30 bg-primary/[0.07] text-primary-light',
  success: 'border-success/30 bg-success/[0.07] text-success',
  warning: 'border-warning/30 bg-warning/[0.07] text-warning',
  destructive: 'border-error/25 bg-control/80 text-error',
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
        'relative w-full rounded-container border px-ui-md py-ui-sm font-sans text-product-small',
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
    <h5 ref={ref} className={cn('mb-ui-xs font-sans text-product-small font-semibold', className)} {...props} />
  ),
)
AlertTitle.displayName = 'AlertTitle'

const AlertDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-sans text-product-small opacity-90', className)} {...props} />
  ),
)
AlertDescription.displayName = 'AlertDescription'

export { Alert, AlertTitle, AlertDescription }