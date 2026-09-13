import { type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface SegmentedControlItem {
  value: string
  label: ReactNode
  icon?: ReactNode
  disabled?: boolean
}

export interface SegmentedControlProps {
  items: SegmentedControlItem[]
  value: string
  onValueChange: (value: string) => void
  ariaLabel: string
  className?: string
  stretch?: boolean
  size?: 'segment' | 'compact'
}

export function SegmentedControl({
  items,
  value,
  onValueChange,
  ariaLabel,
  className,
  stretch = false,
  size = 'segment',
}: SegmentedControlProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center rounded-control border border-border bg-control p-ui-control-inset',
        stretch && 'flex w-full',
        className,
      )}
    >
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            aria-pressed={active}
            disabled={item.disabled}
            onClick={() => onValueChange(item.value)}
            className={cn(
              'flex min-w-0 items-center justify-center gap-ui-xs rounded-technical border px-ui-sm font-mono font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-50',
              size === 'segment' ? 'h-control-segment text-system-nano' : 'h-control-sm text-system-micro',
              stretch && 'flex-1',
              active
                ? 'border-primary/35 bg-primary/[0.10] text-accent-foreground'
                : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-accent-foreground',
            )}
          >
            {item.icon ? <span className="shrink-0">{item.icon}</span> : null}
            <span className="truncate">{item.label}</span>
          </button>
        )
      })}
    </div>
  )
}
