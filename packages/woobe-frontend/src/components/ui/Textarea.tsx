import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { Textarea as WoobeTextarea } from '@woobe/ui'
import { cn } from '@/lib/utils'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => (
    <div className="w-full">
      <WoobeTextarea ref={ref} invalid={Boolean(error)} className={cn(className)} {...props} />
      {error && <p className="mt-ui-xs font-mono text-system-label text-error">{error}</p>}
    </div>
  ),
)

Textarea.displayName = 'Textarea'

export { Textarea }
