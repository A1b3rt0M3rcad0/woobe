import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, autoComplete, name, ...props }, ref) => {
    const isLegacyTechnicalSecret = type === 'password' && autoComplete === 'new-password' && !name

    return (
      <div className="w-full">
        <input
          type={isLegacyTechnicalSecret ? 'text' : type}
          name={name}
          autoComplete={isLegacyTechnicalSecret ? 'off' : autoComplete}
          data-form-type={isLegacyTechnicalSecret ? 'other' : undefined}
          data-1p-ignore={isLegacyTechnicalSecret ? true : undefined}
          data-lpignore={isLegacyTechnicalSecret ? 'true' : undefined}
          className={cn(
            'flex h-9 w-full rounded-lg border border-border bg-transparent px-3 py-1 text-sm shadow-sm transition-colors',
            'placeholder:text-muted',
            'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary',
            'disabled:cursor-not-allowed disabled:opacity-50',
            isLegacyTechnicalSecret && '[-webkit-text-security:disc]',
            error && 'border-red-500 focus-visible:ring-red-500',
            className,
          )}
          ref={ref}
          {...props}
        />
        {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      </div>
    )
  },
)
Input.displayName = 'Input'

export { Input }
