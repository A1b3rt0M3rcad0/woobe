import { Search, X } from 'lucide-react'
import { type ReactNode } from 'react'
import { EmptyStatePanel } from './EmptyStatePanel'
import { Input } from './Input'
import { SegmentedControl } from './SegmentedControl'
import { cn } from '../lib/cn'
import '../styles/resource-page-compatibility.css'

export type ResourcePageVariant = 'contained' | 'canvas'

export interface ResourcePageProps {
  title: string
  description: string
  eyebrow?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  variant?: ResourcePageVariant
}

export function ResourcePage({
  title,
  description,
  eyebrow,
  action,
  children,
  className,
  variant = 'contained',
}: ResourcePageProps) {
  const canvas = variant === 'canvas'

  return (
    <div
      className={cn(
        'resource-page-shell w-full font-sans',
        canvas ? 'max-w-none' : 'mx-auto max-w-resource space-y-ui-lg',
        '[&_label]:font-mono [&_legend]:font-mono [&_button]:font-mono [&_input]:text-system-control',
        '[&_select]:font-sans [&_select]:text-system-control [&_select]:font-normal [&_select]:text-slate-100 [&_select]:outline-none',
        '[&_th]:font-mono [&_dt]:font-mono [&_code]:font-mono [&_pre]:font-mono',
        '[&_.uppercase]:font-mono [&_.tabular-nums]:font-mono',
        '[&_textarea]:font-sans',
        '[&_.rounded-2xl]:rounded-container [&_.rounded-xl]:rounded-container [&_.rounded-lg]:rounded-control [&_.rounded-md]:rounded-technical',
        '[&_.shadow-sm]:shadow-none [&_.shadow-lg]:shadow-none [&_.shadow-xl]:shadow-none [&_.shadow-2xl]:shadow-none',
        className,
      )}
    >
      <ResourcePageHeader
        title={title}
        description={description}
        eyebrow={eyebrow}
        action={action}
        variant={variant}
      />
      {canvas ? (
        <div className="space-y-ui-stack px-ui-content-gutter py-ui-lg sm:px-ui-content-gutter">
          {children}
        </div>
      ) : children}
    </div>
  )
}

export function ResourcePageHeader({
  title,
  description,
  eyebrow,
  action,
  variant = 'contained',
}: Pick<ResourcePageProps, 'title' | 'description' | 'eyebrow' | 'action' | 'variant'>) {
  const canvas = variant === 'canvas'

  return (
    <header
      className={cn(
        'bg-surface/[0.96] shadow-none',
        canvas
          ? 'flex min-h-project-sidebar-header w-full items-center border-b border-border px-ui-content-gutter py-ui-md'
          : 'border border-border px-ui-lg py-ui-md',
      )}
    >
      <div className="flex w-full flex-col gap-ui-md md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <div className="mb-ui-sm flex items-center gap-ui-sm font-mono text-system-meta font-bold uppercase tracking-ui-eyebrow text-muted-foreground">
              <span className="h-ui-xs w-ui-xs bg-primary" />
              {eyebrow}
            </div>
          ) : null}
          <h1 className={cn('font-sans font-semibold text-slate-50', canvas ? 'text-page-title' : 'text-heading')}>{title}</h1>
          <p className="mt-ui-xs max-w-3xl font-sans text-product-small text-muted-foreground">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </header>
  )
}

export function ResourceToolbar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'resource-toolbar flex flex-col gap-ui-sm rounded-container border border-border bg-surface/[0.92] p-ui-sm shadow-none',
        '[&_input]:h-control-sm [&_select]:h-control-sm',
        className,
      )}
    >
      {children}
    </div>
  )
}

export interface ResourceTab<T extends string> {
  value: T
  label: string
  count?: number
}

function ResourceCount({ children, compact = false }: { children: ReactNode; compact?: boolean }) {
  return (
    <span className={cn(
      'shrink-0 font-mono font-normal tabular-nums text-muted-foreground',
      compact ? 'text-system-nano' : 'text-system-meta',
    )}>
      {children}
    </span>
  )
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
      <SegmentedControl
        ariaLabel={label}
        value={value}
        onValueChange={(next) => onChange(next as T)}
        size="technical"
        className="p-ui-hairline [&>button]:!h-control-xs [&>button]:!px-[7px] [&>button]:!text-[9px] [&>button]:!leading-[12px]"
        items={tabs.map((tab) => ({
          value: tab.value,
          label: (
            <span className="flex min-w-0 items-center gap-ui-xs">
              <span className="truncate">{tab.label}</span>
              {tab.count !== undefined ? <ResourceCount compact>{tab.count}</ResourceCount> : null}
            </span>
          ),
        }))}
      />
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
      <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
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
        className="h-control-sm pl-8 pr-8 font-sans text-system-control"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-ui-xs top-1/2 flex h-control-xs w-control-xs -translate-y-1/2 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-accent/50 hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          <X className="h-icon-sm w-icon-sm" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  )
}

export function ResourceSectionHeader({ title, description, count }: { title: string; description?: string; count?: ReactNode }) {
  return (
    <div className="mb-ui-md flex items-center gap-ui-md">
      <span className="h-1.5 w-1.5 shrink-0 bg-primary" />
      <div className="min-w-0">
        <div className="flex items-center gap-ui-sm">
          <h2 className="font-mono text-system-control font-bold uppercase tracking-ui-eyebrow text-slate-50">{title}</h2>
          {count !== undefined ? <ResourceCount>{count}</ResourceCount> : null}
        </div>
        {description ? <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{description}</p> : null}
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
  return <EmptyStatePanel icon={icon} title={title} description={description} action={action} className={className} />
}
