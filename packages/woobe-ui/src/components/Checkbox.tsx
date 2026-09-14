import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(({ className, disabled, ...props }, ref) => (
  <input
    ref={ref}
    type="checkbox"
    disabled={disabled}
    className={cn(
      'h-3.5 w-3.5 shrink-0 cursor-pointer rounded-technical border border-border bg-control accent-primary',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
      'disabled:cursor-not-allowed disabled:opacity-45',
      className,
    )}
    {...props}
  />
))
Checkbox.displayName = 'Checkbox'

export { Checkbox }
