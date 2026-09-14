import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { FieldError, Textarea as WoobeTextarea } from '@woobe/ui'
import { cn } from '@/lib/utils'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => (
    <div className="w-full">
      <WoobeTextarea ref={ref} invalid={Boolean(error)} className={cn(className)} {...props} />
      {error ? <FieldError className="mt-ui-xs">{error}</FieldError> : null}
    </div>
  ),
)

Textarea.displayName = 'Textarea'

export { Textarea }