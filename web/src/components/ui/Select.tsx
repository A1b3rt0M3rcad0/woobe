import { forwardRef, useMemo, useState, type ChangeEvent, type SelectHTMLAttributes } from 'react'
import { Check, ChevronDown, Search } from 'lucide-react'

import { cn } from '@/lib/utils'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

const SEARCHABLE_THRESHOLD = 30
const MAX_VISIBLE_OPTIONS = 100

function splitOptionLabel(label: string) {
  const [title, ...rest] = label.split(' · ')
  return {
    title: title || label,
    subtitle: rest.join(' · '),
  }
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, error, options, placeholder, disabled, value, defaultValue, onChange, ...props }, ref) => {
    const [query, setQuery] = useState('')
    const selectedValue = String(value ?? defaultValue ?? '')
    const selectedOption = options.find((option) => option.value === selectedValue)
    const searchable = !disabled && options.length > SEARCHABLE_THRESHOLD
    const normalizedQuery = query.trim().toLowerCase()

    const filteredOptions = useMemo(() => {
      if (!normalizedQuery) return options

      return options.filter((option) => `${option.label} ${option.value}`.toLowerCase().includes(normalizedQuery))
    }, [normalizedQuery, options])

    const visibleOptions = filteredOptions.slice(0, MAX_VISIBLE_OPTIONS)
    const hiddenCount = Math.max(filteredOptions.length - visibleOptions.length, 0)

    const handleValueChange = (nextValue: string) => {
      const event = {
        target: { value: nextValue },
        currentTarget: { value: nextValue },
      } as ChangeEvent<HTMLSelectElement>

      onChange?.(event)
    }

    if (searchable) {
      return (
        <div className="w-full">
          <select
            ref={ref}
            value={selectedValue}
            disabled={disabled}
            onChange={onChange}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            {...props}
          >
            {placeholder && <option value="" disabled>{placeholder}</option>}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <div className={cn('rounded-xl border border-border/80 bg-background/55', error && 'border-red-500')}>
            <div className="border-b border-border/70 p-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={selectedOption ? selectedOption.label : placeholder || 'Search options'}
                  className="h-9 w-full rounded-lg border border-border bg-transparent px-9 py-1 text-sm text-white outline-none transition-colors placeholder:text-muted focus:border-primary/60 focus:ring-1 focus:ring-primary/40"
                />
              </div>
            </div>

            {selectedOption && !normalizedQuery && (
              <div className="border-b border-border/70 px-3 py-2">
                <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Selected</p>
                <p className="mt-1 truncate text-sm font-medium text-white">{splitOptionLabel(selectedOption.label).title}</p>
                <code className="mt-0.5 block truncate text-xs text-muted">{splitOptionLabel(selectedOption.label).subtitle || selectedOption.value}</code>
              </div>
            )}

            <div className="scrollbar-thin max-h-72 overflow-y-auto">
              {visibleOptions.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-muted">No options found.</div>
              ) : visibleOptions.map((option) => {
                const selected = option.value === selectedValue
                const disabledOption = option.value === ''
                const { title, subtitle } = splitOptionLabel(option.label)

                return (
                  <button
                    key={option.value}
                    type="button"
                    disabled={disabledOption}
                    onClick={() => handleValueChange(option.value)}
                    className={cn(
                      'grid w-full gap-1 border-b border-border/60 px-4 py-3 text-left transition-colors last:border-b-0 disabled:cursor-not-allowed disabled:opacity-60',
                      selected ? 'bg-primary/5' : 'hover:bg-surface/70',
                    )}
                  >
                    <span className="flex min-w-0 items-center justify-between gap-3">
                      <span className="truncate text-sm font-medium text-white">{title}</span>
                      {selected && <Check className="h-4 w-4 shrink-0 text-primary-light" />}
                    </span>
                    <code className="block truncate text-xs text-muted">{subtitle || option.value}</code>
                  </button>
                )
              })}
            </div>

            {hiddenCount > 0 && (
              <div className="border-t border-border/70 px-4 py-2 text-xs text-muted">+{hiddenCount} more option(s). Refine the search.</div>
            )}
          </div>

          {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
        </div>
      )
    }

    return (
      <div className="relative w-full">
        <select
          className={cn(
            'flex h-9 w-full rounded-lg border border-border bg-transparent px-3 py-1 text-sm shadow-sm transition-colors appearance-none cursor-pointer',
            'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary',
            'disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-red-500 focus-visible:ring-red-500',
            className,
          )}
          ref={ref}
          disabled={disabled}
          value={value}
          defaultValue={defaultValue}
          onChange={onChange}
          {...props}
        >
          {placeholder && <option value="" disabled>{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-surface text-white">
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      </div>
    )
  },
)
Select.displayName = 'Select'

export { Select }
