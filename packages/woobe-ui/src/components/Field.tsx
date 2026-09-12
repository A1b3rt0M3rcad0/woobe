import { forwardRef, type HTMLAttributes, type LabelHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

const Field = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('grid gap-1.5', className)} {...props} />
  ),
)
Field.displayName = 'Field'

const FieldLabel = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        'font-mono text-[10px] font-medium uppercase leading-none tracking-[0.08em] text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
)
FieldLabel.displayName = 'FieldLabel'

const FieldDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-mono text-[9px] leading-4 text-muted-foreground', className)} {...props} />
  ),
)
FieldDescription.displayName = 'FieldDescription'

const FieldError = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('font-mono text-[9px] leading-4 text-red-400', className)} {...props} />
  ),
)
FieldError.displayName = 'FieldError'

export { Field, FieldLabel, FieldDescription, FieldError }
