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
  density?: 'technical' | 'compact' | 'default'
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
    const technical = density === 'technical'
    const compact = density === 'compact'
    const card = presentation === 'card'
    const row = presentation === 'row'
    const plain = presentation === 'plain'
    const columns = leading && trailing
      ? 'grid-cols-[auto_minmax(0,1fr)_auto]'
      : leading
        ? 'grid-cols-[auto_minmax(0,1fr)]'
        : trailing
          ? 'grid-cols-[minmax(0,1fr)_auto]'
          : 'grid-cols-1'

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

    const densitySpacing = technical
      ? 'gap-ui-control-gap px-ui-sm py-ui-control-gap'
      : compact
        ? 'gap-ui-sm px-ui-sm py-ui-xs'
        : 'gap-ui-md px-ui-md py-ui-control-gap'

    const rowSpacing = technical
      ? 'gap-ui-control-gap px-ui-sm py-ui-control-gap'
      : 'gap-ui-sm px-ui-sm py-ui-sm'

    const labelSize = technical ? 'text-system-control' : compact ? 'text-system-control' : 'text-system-value'
    const technicalDescriptionSize = technical ? 'text-system-meta' : 'text-system-nano'
    const productDescriptionSize = technical
      ? 'text-product-caption'
      : presentation === 'card'
        ? 'text-product-caption'
        : 'text-system-micro'
    const metaSize = technical ? 'text-system-meta' : 'text-system-nano'

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
          'grid min-w-0 w-full items-center text-left transition-colors',
          columns,
          card && 'rounded-container border',
          card && densitySpacing,
          row && 'border-b border-border/75 last:border-b-0',
          row && rowSpacing,
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
        {leading ? <span className="shrink-0">{leading}</span> : null}
        <span className="min-w-0">
          <span className={cn(
            'block font-mono font-semibold',
            labelSize,
            multiline ? 'whitespace-normal break-words' : 'truncate',
            selected ? 'text-accent-foreground' : 'text-accent-foreground/85',
          )}>
            {label}
          </span>
          {description ? (
            <span className={cn(
              'mt-ui-hairline block text-muted-foreground',
              descriptionVariant === 'technical'
                ? cn('font-mono', technicalDescriptionSize)
                : cn('font-sans', productDescriptionSize),
              multiline ? 'whitespace-normal break-words' : 'truncate',
            )}>
              {description}
            </span>
          ) : null}
          {meta ? (
            <span className={cn(
              'mt-ui-hairline flex min-w-0 flex-wrap items-center gap-x-ui-sm gap-y-ui-xs font-mono text-muted-foreground',
              metaSize,
            )}>
              {meta}
            </span>
          ) : null}
        </span>
        {trailing ? <span className="shrink-0">{trailing}</span> : null}
      </div>
    )
  },
)
TechnicalListItem.displayName = 'TechnicalListItem'

export { TechnicalListItem }
