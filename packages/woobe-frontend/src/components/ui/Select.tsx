import { forwardRef, type SelectHTMLAttributes } from 'react'
import { Select as WoobeSelect } from '@woobe/ui'
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
        className={cn(className)}
        {...props}
      />
      {error && <p className="mt-1 font-mono text-[9px] text-red-300">{error}</p>}
    </div>
  ),
)

Select.displayName = 'Select'

export { Select }
