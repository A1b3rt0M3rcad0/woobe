import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid = false, disabled, ...props }, ref) => (
    <textarea
      ref={ref}
      disabled={disabled}
      aria-invalid={invalid || props['aria-invalid'] || undefined}
      className={cn(
        'min-h-textarea w-full resize-y rounded-control border border-border bg-control px-ui-md py-ui-sm font-sans text-product-body text-accent-foreground',
        'placeholder:text-muted-foreground/70 transition-[border-color,box-shadow,background-color]',
        'hover:border-muted focus-visible:border-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/30',
        'aria-[invalid=true]:border-error/70 aria-[invalid=true]:focus-visible:ring-error/30',
        'disabled:cursor-not-allowed disabled:bg-background/30 disabled:text-muted-foreground disabled:opacity-60',
        className,
      )}
      {...props}
    />
  ),
)

Textarea.displayName = 'Textarea'

export { Textarea }
