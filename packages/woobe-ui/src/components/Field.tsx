import { forwardRef, type HTMLAttributes, type LabelHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

const Field = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('grid gap-ui-sm', className)} {...props} />
  ),
)
Field.displayName = 'Field'

const FieldLabel = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        'font-mono text-system-control font-medium uppercase leading-none tracking-ui-label text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
)
FieldLabel.displayName = 'FieldLabel'

const FieldDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-sans text-product-caption text-muted-foreground', className)} {...props} />
  ),
)
FieldDescription.displayName = 'FieldDescription'

const FieldError = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-sans text-product-caption text-error', className)} {...props} />
  ),
)
FieldError.displayName = 'FieldError'

export { Field, FieldLabel, FieldDescription, FieldError }
