import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface ReadOnlyFieldProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode
  value: ReactNode
  description?: ReactNode
  descriptionVariant?: 'product' | 'technical'
}

/** Readable summaries of configured values, matching the settings field hierarchy. */
const ReadOnlyField = forwardRef<HTMLDivElement, ReadOnlyFieldProps>(
  ({ className, label, value, description, descriptionVariant = 'product', ...props }, ref) => (
    <div ref={ref} className={cn('min-w-0 rounded-container border border-border/80 bg-background/55 p-ui-md', className)} {...props}>
      <p className="font-mono text-product-caption font-medium uppercase tracking-ui-field-label text-muted">{label}</p>
      <p className="mt-ui-xs whitespace-pre-wrap break-words font-sans text-product-small font-medium text-accent-foreground">{value}</p>
      {description ? (
        <p className={cn('mt-ui-xs break-words text-product-caption text-muted-foreground', descriptionVariant === 'technical' ? 'font-mono' : 'font-sans')}>
          {description}
        </p>
      ) : null}
    </div>
  ),
)
ReadOnlyField.displayName = 'ReadOnlyField'

export { ReadOnlyField }
