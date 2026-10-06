import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from './Button'
import {
  buildWoobeCalendarDays,
  isWoobeCalendarDayDisabled,
} from './WoobeDateTimePicker'

export function formatWoobeDate(value: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(value)
}

export function WoobeDatePicker({
  value,
  onChange,
  minDate = new Date(),
  className,
}: {
  value: Date | null
  onChange: (value: Date) => void
  minDate?: Date
  className?: string
}) {
  const [month, setMonth] = useState(() => value ?? minDate)
  useEffect(() => {
    if (value) setMonth(value)
  }, [value?.getTime()])
  const sameDay = (left: Date, right: Date) =>
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()

  return (
    <div
      className={cn(
        'rounded-container border border-border bg-control p-ui-md',
        className,
      )}
      role="group"
      aria-label="Expiration calendar"
    >
      <div className="flex items-center justify-between gap-ui-sm">
        <Button
          size="iconSm"
          variant="ghost"
          aria-label="Previous month"
          onClick={() =>
            setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))
          }
        >
          <ChevronLeft className="h-icon w-icon" />
        </Button>
        <p className="font-mono text-system-control font-semibold">
          {new Intl.DateTimeFormat(undefined, {
            month: 'long',
            year: 'numeric',
          }).format(month)}
        </p>
        <Button
          size="iconSm"
          variant="ghost"
          aria-label="Next month"
          onClick={() =>
            setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))
          }
        >
          <ChevronRight className="h-icon w-icon" />
        </Button>
      </div>
      <div className="mt-ui-sm grid grid-cols-7 gap-ui-hairline">
        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day) => (
          <span
            key={day}
            className="pb-ui-xs text-center font-mono text-system-meta text-muted-foreground"
          >
            {day}
          </span>
        ))}
        {buildWoobeCalendarDays(month).map(({ date, outsideMonth }) => {
          const selected = value !== null && sameDay(date, value)
          return (
            <button
              key={date.toISOString()}
              type="button"
              aria-label={formatWoobeDate(date)}
              aria-pressed={selected}
              disabled={isWoobeCalendarDayDisabled(date, minDate)}
              onClick={() => onChange(date)}
              className={cn(
                  'flex h-control-xs items-center justify-center rounded-control font-mono text-system-control transition-colors disabled:cursor-not-allowed disabled:opacity-20',
                outsideMonth
                  ? 'text-muted-foreground/40'
                  : 'text-muted-foreground',
                selected
                  ? 'bg-primary text-accent-foreground'
                  : 'hover:bg-accent hover:text-accent-foreground',
                !selected &&
                  sameDay(date, new Date()) &&
                  'ring-1 ring-inset ring-primary/35',
              )}
            >
              {date.getDate()}
            </button>
          )
        })}
      </div>
    </div>
  )
}
