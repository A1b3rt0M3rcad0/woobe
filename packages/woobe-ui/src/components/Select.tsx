import { forwardRef, type SelectHTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
  options: SelectOption[]
  placeholder?: string
}

const optionClassName = 'bg-surface !font-mono !text-system-control font-normal text-accent-foreground'

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, invalid = false, options, placeholder, disabled, ...props }, ref) => (
    <div className="relative w-full">
      <select
        ref={ref}
        disabled={disabled}
        aria-invalid={invalid || props['aria-invalid'] || undefined}
        className={cn(
          'flex h-control w-full appearance-none rounded-control border border-border bg-control px-ui-md py-ui-xs pr-8 !font-mono !text-system-control font-normal text-accent-foreground',
          'transition-[border-color,box-shadow,background-color] hover:border-muted focus-visible:border-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/30',
          'aria-[invalid=true]:border-error/70 aria-[invalid=true]:focus-visible:ring-error/30',
          'disabled:cursor-not-allowed disabled:bg-background/30 disabled:text-muted-foreground disabled:opacity-60',
          className,
        )}
        {...props}
      >
        {placeholder ? <option value="" disabled className={optionClassName}>{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} className={optionClassName}>
            {option.label}
          </option>
        ))}
      </select>
      <svg
        viewBox="0 0 16 16"
        aria-hidden="true"
        className="pointer-events-none absolute right-ui-sm top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground"
        fill="none"
      >
        <path d="M4.5 6.25 8 9.75l3.5-3.5" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  ),
)

Select.displayName = 'Select'

export { Select }
