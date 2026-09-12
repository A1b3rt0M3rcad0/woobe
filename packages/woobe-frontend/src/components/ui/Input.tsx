import { forwardRef, type InputHTMLAttributes } from 'react'
import { Input as WoobeInput } from '@woobe/ui'
import { cn } from '@/lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, autoComplete, name, ...props }, ref) => {
    const isLegacyTechnicalSecret = type === 'password' && autoComplete === 'new-password' && !name

    return (
      <div className="w-full">
        <WoobeInput
          ref={ref}
          type={isLegacyTechnicalSecret ? 'text' : type}
          name={name}
          autoComplete={isLegacyTechnicalSecret ? 'off' : autoComplete}
          data-form-type={isLegacyTechnicalSecret ? 'other' : undefined}
          data-1p-ignore={isLegacyTechnicalSecret ? true : undefined}
          data-lpignore={isLegacyTechnicalSecret ? 'true' : undefined}
          invalid={Boolean(error)}
          className={cn(isLegacyTechnicalSecret && '[-webkit-text-security:disc]', className)}
          {...props}
        />
        {error && <p className="mt-1 font-mono text-[9px] text-red-300">{error}</p>}
      </div>
    )
  },
)

Input.displayName = 'Input'

export { Input }
