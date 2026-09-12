import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Minus,
  Plus,
} from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from './Button'

export interface WoobeDateTimePickerProps {
  value: Date | null
  onChange: (value: Date | null) => void
  minDate?: Date
  className?: string
  autoOpen?: boolean
}

export interface WoobeCalendarDay {
  date: Date
  outsideMonth: boolean
}

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const PICKER_WIDTH = '20.5rem'
const PLACEMENT_THRESHOLD_PX = 370

function cloneDate(value: Date): Date {
  return new Date(value.getTime())
}

function startOfDay(value: Date): Date {
  const date = cloneDate(value)
  date.setHours(0, 0, 0, 0)
  return date
}

function sameDay(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate()
  )
}

export function buildWoobeCalendarDays(month: Date): WoobeCalendarDay[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  const gridStart = new Date(first)
  gridStart.setDate(first.getDate() - first.getDay())

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart)
    date.setDate(gridStart.getDate() + index)
    return {
      date,
      outsideMonth: date.getMonth() !== month.getMonth(),
    }
  })
}

export function isWoobeCalendarDayDisabled(date: Date, minDate: Date): boolean {
  return startOfDay(date).getTime() < startOfDay(minDate).getTime()
}

export function mergeWoobeDateAndTime(date: Date, time: Date): Date {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    time.getHours(),
    time.getMinutes(),
    0,
    0,
  )
}

export function formatWoobeDateTime(value: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(value)
}

function monthLabel(value: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'long',
    year: 'numeric',
  }).format(value)
}

function timeZoneOffset(value: Date): string {
  const totalMinutes = -value.getTimezoneOffset()
  const sign = totalMinutes >= 0 ? '+' : '-'
  const absoluteMinutes = Math.abs(totalMinutes)
  const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, '0')
  const minutes = String(absoluteMinutes % 60).padStart(2, '0')
  return `UTC${sign}${hours}:${minutes}`
}

function timeZoneLabel(value: Date): string {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local time'
  return `${timeZone} · ${timeZoneOffset(value)}`
}

function defaultFutureDate(minDate: Date): Date {
  const value = new Date(Math.max(Date.now(), minDate.getTime()))
  value.setMinutes(value.getMinutes() + 5, 0, 0)
  return value
}

function normalizeSelectedDay(day: Date, current: Date, minDate: Date): Date {
  let next = mergeWoobeDateAndTime(day, current)
  if (sameDay(day, minDate) && next <= minDate) {
    next = defaultFutureDate(minDate)
  }
  return next
}

function TimeUnitControl({
  value,
  unit,
  onDecrease,
  onIncrease,
}: {
  value: number
  unit: 'hour' | 'minute'
  onDecrease: () => void
  onIncrease: () => void
}) {
  return (
    <div className="flex items-center gap-ui-xs">
      <Button type="button" variant="ghost" size="iconSm" onClick={onDecrease} className="text-muted-foreground" aria-label={`Decrease ${unit}`}>
        <Minus className="h-icon w-icon" />
      </Button>
      <span className="w-control-nav text-center font-mono text-metric font-semibold tabular-nums text-accent-foreground">
        {String(value).padStart(2, '0')}
      </span>
      <Button type="button" variant="ghost" size="iconSm" onClick={onIncrease} className="text-muted-foreground" aria-label={`Increase ${unit}`}>
        <Plus className="h-icon w-icon" />
      </Button>
    </div>
  )
}

export function WoobeDateTimePicker({
  value,
  onChange,
  minDate = new Date(),
  className,
  autoOpen = false,
}: WoobeDateTimePickerProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [openAbove, setOpenAbove] = useState(false)
  const [draft, setDraft] = useState<Date>(() => value ? cloneDate(value) : defaultFutureDate(minDate))
  const [visibleMonth, setVisibleMonth] = useState<Date>(() => new Date(draft.getFullYear(), draft.getMonth(), 1))

  const days = useMemo(() => buildWoobeCalendarDays(visibleMonth), [visibleMonth])
  const isValid = draft.getTime() > minDate.getTime()

  const openPicker = () => {
    const next = value ? cloneDate(value) : defaultFutureDate(minDate)
    setDraft(next)
    setVisibleMonth(new Date(next.getFullYear(), next.getMonth(), 1))
    const triggerRect = triggerRef.current?.getBoundingClientRect()
    if (triggerRect) {
      setOpenAbove(window.innerHeight - triggerRect.bottom < PLACEMENT_THRESHOLD_PX && triggerRect.top > PLACEMENT_THRESHOLD_PX)
    }
    setOpen(true)
  }

  useEffect(() => {
    if (!autoOpen) return
    const frame = window.requestAnimationFrame(openPicker)
    return () => window.cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: PointerEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      setOpen(false)
      triggerRef.current?.focus()
    }

    document.addEventListener('pointerdown', handlePointerDown, true)
    document.addEventListener('keydown', handleEscape, true)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true)
      document.removeEventListener('keydown', handleEscape, true)
    }
  }, [open])

  const changeMonth = (delta: number) => {
    setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + delta, 1))
  }

  const changeHour = (delta: number) => {
    setDraft((current) => {
      const next = cloneDate(current)
      next.setHours(next.getHours() + delta)
      return next
    })
  }

  const changeMinute = (delta: number) => {
    setDraft((current) => {
      const next = cloneDate(current)
      next.setMinutes(next.getMinutes() + delta)
      return next
    })
  }

  const selectDay = (day: Date) => {
    if (isWoobeCalendarDayDisabled(day, minDate)) return
    setDraft((current) => normalizeSelectedDay(day, current, minDate))
  }

  const apply = () => {
    if (!isValid) return
    const normalized = cloneDate(draft)
    normalized.setSeconds(0, 0)
    onChange(normalized)
    setOpen(false)
    triggerRef.current?.focus()
  }

  const clear = () => {
    onChange(null)
    setOpen(false)
    triggerRef.current?.focus()
  }

  return (
    <div ref={wrapperRef} className={cn('relative', className)}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => open ? setOpen(false) : openPicker()}
        aria-expanded={open}
        className="flex h-control w-full items-center gap-ui-sm rounded-control border border-border bg-control px-ui-md text-left transition-colors hover:border-primary/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
      >
        <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-border bg-background/55 text-primary-light">
          <CalendarDays className="h-icon w-icon" />
        </span>
        <span className="min-w-0 flex-1 truncate font-sans text-product-small text-accent-foreground/90">
          {value ? formatWoobeDateTime(value) : 'Select date and time'}
        </span>
        <span className="shrink-0 font-mono text-system-control text-muted-foreground">
          {value ? timeZoneOffset(value) : 'Local'}
        </span>
      </button>

      {open ? (
        <div
          className={cn(
            'absolute left-0 z-popover max-w-[calc(100vw-2rem)] rounded-container border border-border bg-surface p-ui-md shadow-popup',
            openAbove ? 'bottom-[calc(100%+0.5rem)]' : 'top-[calc(100%+0.5rem)]',
          )}
          style={{ width: PICKER_WIDTH }}
        >
          <div className="flex items-center justify-between">
            <Button type="button" variant="outline" size="iconSm" onClick={() => changeMonth(-1)} className="text-muted-foreground" aria-label="Previous month">
              <ChevronLeft className="h-icon-lg w-icon-lg" />
            </Button>
            <p className="font-mono text-system-control font-semibold text-accent-foreground">{monthLabel(visibleMonth)}</p>
            <Button type="button" variant="outline" size="iconSm" onClick={() => changeMonth(1)} className="text-muted-foreground" aria-label="Next month">
              <ChevronRight className="h-icon-lg w-icon-lg" />
            </Button>
          </div>

          <div className="mt-ui-md grid grid-cols-7 gap-ui-hairline">
            {WEEKDAYS.map((weekday) => (
              <span key={weekday} className="pb-ui-xs text-center font-mono text-system-meta font-semibold text-muted-foreground">
                {weekday}
              </span>
            ))}
            {days.map(({ date, outsideMonth }) => {
              const disabled = isWoobeCalendarDayDisabled(date, minDate)
              const selected = sameDay(date, draft)
              const today = sameDay(date, new Date())
              return (
                <button
                  key={date.toISOString()}
                  type="button"
                  disabled={disabled}
                  onClick={() => selectDay(date)}
                  className={cn(
                    'relative flex h-control-sm items-center justify-center rounded-control font-mono text-system-control transition-colors',
                    outsideMonth && 'text-muted-foreground/40',
                    !outsideMonth && !selected && 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    today && !selected && 'ring-1 ring-inset ring-primary/35 text-accent-foreground',
                    selected && 'bg-primary text-accent-foreground hover:bg-primary-hover',
                    disabled && 'cursor-not-allowed opacity-20 hover:bg-transparent hover:text-muted-foreground',
                  )}
                >
                  {date.getDate()}
                </button>
              )
            })}
          </div>

          <div className="mt-ui-md border-t border-border pt-ui-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-ui-sm font-mono text-system-label font-medium text-muted-foreground">
                <Clock3 className="h-icon w-icon" />
                <span>Time</span>
              </div>
              <span className="font-mono text-system-control text-muted-foreground">{timeZoneOffset(draft)}</span>
            </div>

            <div className="mt-ui-sm flex items-center justify-center gap-ui-sm">
              <TimeUnitControl unit="hour" value={draft.getHours()} onDecrease={() => changeHour(-1)} onIncrease={() => changeHour(1)} />
              <span className="font-mono text-heading font-semibold text-muted-foreground">:</span>
              <TimeUnitControl unit="minute" value={draft.getMinutes()} onDecrease={() => changeMinute(-1)} onIncrease={() => changeMinute(1)} />
            </div>

            <div className="mt-ui-sm text-center">
              <p className={cn('font-sans text-product-small font-medium', isValid ? 'text-accent-foreground' : 'text-error')}>
                {isValid ? formatWoobeDateTime(draft) : 'Choose a future date and time'}
              </p>
              <p className="mt-ui-xs font-mono text-system-control text-muted-foreground">{timeZoneLabel(draft)}</p>
            </div>
          </div>

          <div className="mt-ui-md flex items-center justify-between border-t border-border pt-ui-md">
            <Button type="button" variant="ghost" size="sm" onClick={clear}>Clear</Button>
            <Button type="button" size="sm" onClick={apply} disabled={!isValid}>Apply</Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
