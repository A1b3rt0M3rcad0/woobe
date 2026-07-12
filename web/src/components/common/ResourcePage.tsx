import type { ReactNode } from 'react'
import { Search, X } from 'lucide-react'

import { Input } from '@/components/ui/Input'
import { cn } from '@/lib/utils'

interface ResourcePageProps {
  title: string
  description: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function ResourcePage({ title, description, action, children, className }: ResourcePageProps) {
  return (
    <div className={cn('mx-auto w-full max-w-[1500px] space-y-6', className)}>
      <ResourcePageHeader title={title} description={description} action={action} />
      {children}
    </div>
  )
}

export function ResourcePageHeader({
  title,
  description,
  action,
}: Pick<ResourcePageProps, 'title' | 'description' | 'action'>) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function ResourceToolbar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-4 rounded-xl border border-border/80 bg-surface/45 p-4', className)}>
      {children}
    </div>
  )
}

export interface ResourceTab<T extends string> {
  value: T
  label: string
  count?: number
}

export function ResourceTabs<T extends string>({
  value,
  tabs,
  onChange,
  label,
}: {
  value: T
  tabs: Array<ResourceTab<T>>
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div className="scrollbar-thin min-w-0 overflow-x-auto">
      <div className="inline-flex min-w-max rounded-xl border border-border/80 bg-surface/55 p-1" role="tablist" aria-label={label}>
        {tabs.map((tab) => {
          const active = value === tab.value
          return (
            <button
              key={tab.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(tab.value)}
              className={cn(
                'rounded-lg px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
                active ? 'bg-primary/12 text-primary-light' : 'text-muted hover:bg-background/60 hover:text-white',
              )}
            >
              {tab.label}
              {tab.count !== undefined && <span className="ml-1 text-[10px] opacity-70">{tab.count}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function ResourceSearch({
  value,
  onChange,
  placeholder,
  label,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  label: string
  className?: string
}) {
  return (
    <div className={cn('relative min-w-0 flex-1', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
      <Input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && value) {
            event.preventDefault()
            onChange('')
          }
        }}
        placeholder={placeholder}
        aria-label={label}
        className="h-10 pl-9 pr-9"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

export function ResourceSectionHeader({
  title,
  description,
  count,
}: {
  title: string
  description?: string
  count?: ReactNode
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {description && <p className="mt-1 text-xs text-muted">{description}</p>}
      </div>
      {count !== undefined && <span className="shrink-0 text-xs text-muted">{count}</span>}
    </div>
  )
}

export function ResourceEmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  description: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('rounded-xl border border-dashed border-border/80 bg-surface/40 px-6 py-10 text-center', className)}>
      {icon && <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-background/55 text-muted">{icon}</div>}
      <h2 className={cn('text-sm font-semibold text-white', icon && 'mt-3')}>{title}</h2>
      <p className="mx-auto mt-1 max-w-lg text-sm leading-6 text-muted">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}
