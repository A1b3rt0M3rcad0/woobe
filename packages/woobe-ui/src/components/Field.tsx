import { createContext, forwardRef, type HTMLAttributes, type LabelHTMLAttributes, useContext } from 'react'
import { cn } from '../lib/cn'

export type FieldDensity = 'default' | 'technical'

export interface FieldProps extends HTMLAttributes<HTMLDivElement> {
  density?: FieldDensity
}

const FieldDensityContext = createContext<FieldDensity>('default')

const Field = forwardRef<HTMLDivElement, FieldProps>(
  ({ className, density = 'default', ...props }, ref) => (
    <FieldDensityContext.Provider value={density}>
      <div
        ref={ref}
        className={cn(density === 'technical' ? 'grid gap-ui-control-gap' : 'grid gap-ui-xs', className)}
        {...props}
      />
    </FieldDensityContext.Provider>
  ),
)
Field.displayName = 'Field'

const FieldLabel = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => {
    const density = useContext(FieldDensityContext)
    return (
      <label
        ref={ref}
        className={cn(
          'font-mono font-medium uppercase tracking-ui-field-label text-muted',
          density === 'technical' ? 'text-product-caption' : 'text-system-nano',
          className,
        )}
        {...props}
      />
    )
  },
)
FieldLabel.displayName = 'FieldLabel'

const FieldOptional = forwardRef<HTMLSpanElement, HTMLAttributes<HTMLSpanElement>>(
  ({ className, children = '(optional)', ...props }, ref) => {
    const density = useContext(FieldDensityContext)
    return (
      <span
        ref={ref}
        className={cn(
          'ml-ui-xs font-mono font-normal normal-case tracking-normal text-muted-foreground/65',
          density === 'technical' ? 'text-product-caption' : 'text-system-nano',
          className,
        )}
        {...props}
      >
        {children}
      </span>
    )
  },
)
FieldOptional.displayName = 'FieldOptional'

const FieldDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => {
    const density = useContext(FieldDensityContext)
    return (
      <p
        ref={ref}
        className={cn(
          'font-sans text-muted-foreground',
          density === 'technical' ? 'text-product-caption' : 'text-system-micro',
          className,
        )}
        {...props}
      />
    )
  },
)
FieldDescription.displayName = 'FieldDescription'

const FieldError = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => {
    const density = useContext(FieldDensityContext)
    return (
      <p
        ref={ref}
        className={cn(
          'font-sans text-error',
          density === 'technical' ? 'text-product-caption' : 'text-system-micro',
          className,
        )}
        {...props}
      />
    )
  },
)
FieldError.displayName = 'FieldError'

export { Field, FieldLabel, FieldOptional, FieldDescription, FieldError }
