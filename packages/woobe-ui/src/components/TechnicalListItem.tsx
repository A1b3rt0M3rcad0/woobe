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
  title?: string
}

const TechnicalListItem = forwardRef<HTMLDivElement, TechnicalListItemProps>(
  ({ className, label, description, meta, leading, trailing, selected = false, disabled = false, onClick, onKeyDown, title, ...props }, ref) => {
    const interactive = Boolean(onClick)

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
          'grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 rounded-container border px-3 py-2.5 text-left transition-colors',
          selected ? 'border-primary/35 bg-primary/[0.08]' : 'border-border/75 bg-background/25',
          interactive && !disabled && !selected && 'cursor-pointer hover:border-primary/25 hover:bg-control/35',
          interactive && !disabled && selected && 'cursor-pointer hover:bg-primary/[0.11]',
          disabled && 'cursor-not-allowed opacity-50',
          className,
        )}
        {...props}
      >
        {leading ? <span className="shrink-0">{leading}</span> : <span aria-hidden="true" />}
        <span className="min-w-0">
          <span className={cn('block truncate font-mono text-[9px] font-semibold leading-4', selected ? 'text-slate-50' : 'text-slate-200')}>{label}</span>
          {description ? <span className="mt-0.5 block truncate font-sans text-[9px] leading-4 text-muted-foreground">{description}</span> : null}
          {meta ? <span className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[8px] leading-3.5 text-muted-foreground">{meta}</span> : null}
        </span>
        {trailing ? <span className="shrink-0">{trailing}</span> : <span aria-hidden="true" />}
      </div>
    )
  },
)
TechnicalListItem.displayName = 'TechnicalListItem'

export { TechnicalListItem }
