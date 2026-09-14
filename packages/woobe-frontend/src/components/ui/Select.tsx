import { forwardRef, type SelectHTMLAttributes } from 'react'
import { FieldError, Select as WoobeSelect } from '@woobe/ui'
import { cn } from '@/lib/utils'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, error, options, placeholder, ...props }, ref) => (
    <div className="w-full">
      <WoobeSelect
        ref={ref}
        invalid={Boolean(error)}
        options={options}
        placeholder={placeholder}
        className={cn('!h-control', className)}
        {...props}
      />
      {error ? <FieldError className="mt-ui-xs">{error}</FieldError> : null}
    </div>
  ),
)

Select.displayName = 'Select'

export { Select }