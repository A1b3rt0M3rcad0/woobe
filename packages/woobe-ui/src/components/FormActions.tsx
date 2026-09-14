import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface FormActionsProps extends HTMLAttributes<HTMLDivElement> {
  separated?: boolean
}

const FormActions = forwardRef<HTMLDivElement, FormActionsProps>(
  ({ className, separated = true, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex flex-wrap items-center justify-end gap-ui-sm',
        separated && 'border-t border-border pt-ui-md',
        className,
      )}
      {...props}
    />
  ),
)
FormActions.displayName = 'FormActions'

export { FormActions }
