import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Minus,
  Plus,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface WoobeDateTimePickerProps {
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
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={onDecrease}
        className="flex h-7 w-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent hover:text-white"
        aria-label={`Decrease ${unit}`}
      >
        <Minus className="h-3.5 w-3.5" />
      </button>
      <span className="w-9 text-center font-mono text-xl font-semibold tabular-nums text-white">
        {String(value).padStart(2, '0')}
      </span>
      <button
        type="button"
        onClick={onIncrease}
        className="flex h-7 w-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent hover:text-white"
        aria-label={`Increase ${unit}`}
      >
        <Plus className="h-3.5 w-3.5" />
      </button>
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
      setOpenAbove(window.innerHeight - triggerRect.bottom < 370 && triggerRect.top > 370)
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
        className="flex h-10 w-full items-center gap-3 rounded-lg border border-border bg-background/45 px-3 text-left shadow-sm transition-colors hover:border-primary/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-background/70 text-primary-light">
          <CalendarDays className="h-3.5 w-3.5" />
        </span>
        <span className="min-w-0 flex-1 truncate text-xs text-white">
          {value ? formatWoobeDateTime(value) : 'Select date and time'}
        </span>
        <span className="shrink-0 text-[10px] text-muted">
          {value ? timeZoneOffset(value) : 'Local'}
        </span>
      </button>

      {open && (
        <div
          className={cn(
            'absolute left-0 z-[90] w-[328px] max-w-[calc(100vw-2rem)] rounded-2xl border border-border/90 bg-surface p-3.5 shadow-2xl shadow-black/50',
            openAbove ? 'bottom-[calc(100%+8px)]' : 'top-[calc(100%+8px)]',
          )}
        >
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => changeMonth(-1)}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-border/80 text-muted transition-colors hover:border-primary/35 hover:bg-primary/10 hover:text-white"
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <p className="text-sm font-semibold text-white">{monthLabel(visibleMonth)}</p>
            <button
              type="button"
              onClick={() => changeMonth(1)}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-border/80 text-muted transition-colors hover:border-primary/35 hover:bg-primary/10 hover:text-white"
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 grid grid-cols-7 gap-0.5">
            {WEEKDAYS.map((weekday) => (
              <span key={weekday} className="pb-1 text-center text-[9px] font-semibold text-muted">
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
                    'relative flex h-8 items-center justify-center rounded-lg text-[11px] transition-colors',
                    outsideMonth && 'text-muted/40',
                    !outsideMonth && !selected && 'text-muted hover:bg-accent hover:text-white',
                    today && !selected && 'ring-1 ring-inset ring-primary/35 text-white',
                    selected && 'bg-primary text-white shadow-sm shadow-primary/20',
                    disabled && 'cursor-not-allowed opacity-20 hover:bg-transparent hover:text-muted',
                  )}
                >
                  {date.getDate()}
                </button>
              )
            })}
          </div>

          <div className="mt-3 border-t border-border/80 pt-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[11px] font-medium text-muted">
                <Clock3 className="h-3.5 w-3.5" />
                <span>Time</span>
              </div>
              <span className="text-[10px] text-muted">{timeZoneOffset(draft)}</span>
            </div>

            <div className="mt-2.5 flex items-center justify-center gap-2">
              <TimeUnitControl
                unit="hour"
                value={draft.getHours()}
                onDecrease={() => changeHour(-1)}
                onIncrease={() => changeHour(1)}
              />
              <span className="pb-0.5 font-mono text-lg font-semibold text-muted/70">:</span>
              <TimeUnitControl
                unit="minute"
                value={draft.getMinutes()}
                onDecrease={() => changeMinute(-1)}
                onIncrease={() => changeMinute(1)}
              />
            </div>

            <div className="mt-2.5 text-center">
              <p className={cn('text-xs font-medium', isValid ? 'text-white' : 'text-red-300')}>
                {isValid ? formatWoobeDateTime(draft) : 'Choose a future date and time'}
              </p>
              <p className="mt-0.5 text-[10px] text-muted">{timeZoneLabel(draft)}</p>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-border/80 pt-3">
            <button
              type="button"
              onClick={clear}
              className="rounded-lg px-2 py-1.5 text-xs text-muted transition-colors hover:bg-accent hover:text-white"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={apply}
              disabled={!isValid}
              className="h-8 rounded-lg bg-primary px-3 text-xs font-medium text-white shadow-sm transition-colors hover:bg-primary-hover disabled:pointer-events-none disabled:opacity-40"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
