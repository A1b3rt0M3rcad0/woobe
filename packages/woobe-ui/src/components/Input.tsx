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
        'flex h-9 w-full rounded-control border border-border bg-background/65 px-3 py-1.5 text-sm text-slate-100',
        'placeholder:text-muted-foreground/70 transition-[border-color,box-shadow,background-color]',
        'hover:border-slate-600 focus-visible:border-primary/70 focus-visible:bg-background focus-visible:outline-none',
        'focus-visible:ring-2 focus-visible:ring-primary/20',
        'aria-[invalid=true]:border-red-500/70 aria-[invalid=true]:focus-visible:ring-red-500/15',
        'disabled:cursor-not-allowed disabled:bg-background/35 disabled:text-muted-foreground disabled:opacity-60',
        className,
      )}
      {...props}
    />
  ),
)

Input.displayName = 'Input'

export { Input }
