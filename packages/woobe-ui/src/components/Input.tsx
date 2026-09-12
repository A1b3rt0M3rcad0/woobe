import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid = false, disabled, ...props }, ref) => (
    <input
      ref={ref}
      disabled={disabled}
      aria-invalid={invalid || props['aria-invalid'] || undefined}
      className={cn(
        'flex h-control w-full rounded-control border border-border bg-control px-ui-md py-ui-xs font-sans text-product-body text-accent-foreground',
        'placeholder:text-muted-foreground/70 transition-[border-color,box-shadow,background-color]',
        'hover:border-muted focus-visible:border-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/30',
        'aria-[invalid=true]:border-error/55 aria-[invalid=true]:focus-visible:ring-error/20',
        'disabled:cursor-not-allowed disabled:bg-background/30 disabled:text-muted-foreground disabled:opacity-60',
        className,
      )}
      {...props}
    />
  ),
)

Input.displayName = 'Input'

export { Input }
