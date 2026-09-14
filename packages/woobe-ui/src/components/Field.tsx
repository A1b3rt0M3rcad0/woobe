import { forwardRef, type HTMLAttributes, type LabelHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

const Field = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('grid gap-ui-xs', className)} {...props} />
  ),
)
Field.displayName = 'Field'

const FieldLabel = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        'font-mono text-system-nano font-medium uppercase tracking-ui-label text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
)
FieldLabel.displayName = 'FieldLabel'

const FieldOptional = forwardRef<HTMLSpanElement, HTMLAttributes<HTMLSpanElement>>(
  ({ className, children = '(optional)', ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        'ml-ui-xs font-mono text-system-nano font-normal normal-case tracking-normal text-muted-foreground/70',
        className,
      )}
      {...props}
    >
      {children}
    </span>
  ),
)
FieldOptional.displayName = 'FieldOptional'

const FieldDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-sans text-system-micro text-muted-foreground', className)} {...props} />
  ),
)
FieldDescription.displayName = 'FieldDescription'

const FieldError = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-sans text-system-micro text-error', className)} {...props} />
  ),
)
FieldError.displayName = 'FieldError'

export { Field, FieldLabel, FieldOptional, FieldDescription, FieldError }
