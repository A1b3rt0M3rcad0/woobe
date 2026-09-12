import type { ReactNode } from 'react'
import { Search, X } from 'lucide-react'
import { Input } from '@woobe/ui'

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
    <div className={cn('mx-auto w-full max-w-[1500px] space-y-4', className)}>
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
    <header className="border border-border bg-surface/[0.96] px-4 py-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.018)]">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-2 font-mono text-[8px] font-bold uppercase tracking-[0.13em] text-muted-foreground">
            <span className="h-1.5 w-1.5 bg-primary" />
            Project resource
          </div>
          <h1 className="font-mono text-base font-bold tracking-[0.01em] text-slate-50">{title}</h1>
          <p className="mt-1 max-w-3xl font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </header>
  )
}

export function ResourceToolbar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-3 border border-border bg-surface/[0.9] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.012)]', className)}>
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
      <div className="inline-flex min-w-max rounded-control border border-border bg-control p-[3px]" role="tablist" aria-label={label}>
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
                'flex h-[27px] items-center gap-1.5 rounded-technical border px-2.5 font-mono text-[9px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
                active
                  ? 'border-primary/35 bg-primary/[0.12] text-slate-50'
                  : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-slate-200',
              )}
            >
              {tab.label}
              {tab.count !== undefined && <span className="font-mono text-[8px] tabular-nums text-muted-foreground">{tab.count}</span>}
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
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
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
        className="pl-8 pr-8 font-mono text-[10px]"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-accent/50 hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          <X className="h-3 w-3" aria-hidden="true" />
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
    <div className="mb-3 flex items-center gap-2.5">
      <span className="h-1.5 w-1.5 shrink-0 bg-primary" />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.11em] text-slate-50">{title}</h2>
          {count !== undefined && <span className="font-mono text-[8px] tabular-nums text-muted-foreground">{count}</span>}
        </div>
        {description && <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">{description}</p>}
      </div>
      <div className="h-px flex-1 bg-border" />
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
    <div className={cn('border border-dashed border-border bg-surface/[0.72] px-6 py-9 text-center', className)}>
      {icon && <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-muted-foreground">{icon}</div>}
      <h2 className={cn('font-mono text-[11px] font-bold text-slate-50', icon && 'mt-3')}>{title}</h2>
      <p className="mx-auto mt-1 max-w-lg font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}
