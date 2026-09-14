import { forwardRef, type HTMLAttributes, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface TechnicalListItemProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  label: ReactNode
  description?: ReactNode
  meta?: ReactNode
  leading?: ReactNode
  trailing?: ReactNode
  selected?: boolean
  disabled?: boolean
  multiline?: boolean
  density?: 'compact' | 'default'
  presentation?: 'card' | 'row' | 'plain'
  descriptionVariant?: 'product' | 'technical'
  title?: string
}

const TechnicalListItem = forwardRef<HTMLDivElement, TechnicalListItemProps>(
  ({
    className,
    label,
    description,
    meta,
    leading,
    trailing,
    selected = false,
    disabled = false,
    multiline = false,
    density = 'compact',
    presentation = 'card',
    descriptionVariant = 'product',
    onClick,
    onKeyDown,
    title,
    ...props
  }, ref) => {
    const interactive = Boolean(onClick)
    const compact = density === 'compact'
    const card = presentation === 'card'
    const row = presentation === 'row'
    const plain = presentation === 'plain'

    const handleClick = (event: MouseEvent<HTMLDivElement>) => {
      if (disabled) return
      onClick?.(event)
    }

    const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
      onKeyDown?.(event)
      if (event.defaultPrevented || disabled || !interactive || event.target !== event.currentTarget) return
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        event.currentTarget.click()
      }
    }

    return (
      <div
        ref={ref}
        role={interactive ? 'button' : undefined}
        tabIndex={interactive && !disabled ? 0 : undefined}
        aria-disabled={disabled || undefined}
        title={title}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        className={cn(
          'grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center text-left transition-colors',
          card && 'rounded-container border',
          card && (compact ? 'gap-ui-sm px-ui-sm py-ui-xs' : 'gap-ui-md px-ui-md py-ui-control-gap'),
          row && 'gap-ui-sm border-b border-border/75 px-ui-sm py-ui-sm last:border-b-0',
          plain && 'gap-ui-sm border-0 bg-transparent p-0',
          card && (selected ? 'border-primary/35 bg-primary/[0.08]' : 'border-border/75 bg-background/25'),
          row && (selected ? 'bg-primary/[0.08]' : 'bg-transparent'),
          interactive && !disabled && card && !selected && 'cursor-pointer hover:border-primary/25 hover:bg-control/35',
          interactive && !disabled && card && selected && 'cursor-pointer hover:bg-primary/[0.11]',
          interactive && !disabled && row && !selected && 'cursor-pointer hover:bg-control/35',
          interactive && !disabled && row && selected && 'cursor-pointer hover:bg-primary/[0.11]',
          interactive && !disabled && plain && 'cursor-pointer hover:text-accent-foreground',
          disabled && 'cursor-not-allowed opacity-50',
          className,
        )}
        {...props}
      >
        {leading ? <span className="shrink-0">{leading}</span> : <span aria-hidden="true" />}
        <span className="min-w-0">
          <span className={cn(
            'block font-mono font-semibold',
            compact ? 'text-system-control' : 'text-system-value',
            multiline ? 'whitespace-normal break-words' : 'truncate',
            selected ? 'text-accent-foreground' : 'text-accent-foreground/85',
          )}>
            {label}
          </span>
          {description ? (
            <span className={cn(
              'mt-ui-hairline block text-muted-foreground',
              descriptionVariant === 'technical'
                ? 'font-mono text-system-nano'
                : presentation === 'card'
                  ? 'font-sans text-product-caption'
                  : 'font-sans text-system-micro',
              multiline ? 'whitespace-normal break-words' : 'truncate',
            )}>
              {description}
            </span>
          ) : null}
          {meta ? <span className="mt-ui-hairline flex min-w-0 flex-wrap items-center gap-x-ui-sm gap-y-ui-xs font-mono text-system-nano text-muted-foreground">{meta}</span> : null}
        </span>
        {trailing ? <span className="shrink-0">{trailing}</span> : <span aria-hidden="true" />}
      </div>
    )
  },
)
TechnicalListItem.displayName = 'TechnicalListItem'

export { TechnicalListItem }
