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
      {error && <p className="mt-1 font-mono text-[9px] text-red-300">{error}</p>}
    </div>
  ),
)

Textarea.displayName = 'Textarea'

export { Textarea }
