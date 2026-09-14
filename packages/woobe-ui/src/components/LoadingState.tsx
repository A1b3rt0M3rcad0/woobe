import { useEffect, useState, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { Skeleton } from './Skeleton'
import { cn } from '../lib/cn'

export type LoadingVariant = 'page' | 'workspace' | 'panel' | 'inline' | 'fullscreen'
export type LoadingLayout = 'cards' | 'compact-cards' | 'list' | 'resource-list' | 'table' | 'metrics' | 'playground' | 'auth'

export interface LoadingStateProps {
  message?: string
  description?: string
  variant?: LoadingVariant
  layout?: LoadingLayout
  className?: string
  delayMs?: number
}

function useDelayedVisible(delayMs: number) {
  const [visible, setVisible] = useState(delayMs <= 0)
  useEffect(() => {
    if (delayMs <= 0) { setVisible(true); return undefined }
    const timeoutId = window.setTimeout(() => setVisible(true), delayMs)
    return () => window.clearTimeout(timeoutId)
  }, [delayMs])
  return visible
}

function Surface({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('rounded-container border border-border bg-surface/55', className)}>{children}</div>
}

function LoadingMark() {
  return <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Loader2 className="h-icon w-icon animate-spin" /></span>
}

function LoadingHeader({ message, description }: { message: string; description?: string }) {
  return <Surface className="flex items-center gap-ui-md px-ui-lg py-ui-md"><LoadingMark /><div className="min-w-0"><p className="font-mono text-system-control font-semibold text-accent-foreground/85">{message}</p>{description ? <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{description}</p> : null}</div></Surface>
}

function CardSkeleton({ compact = false }: { compact?: boolean }) {
  return <Surface className={compact ? 'p-ui-md' : 'p-ui-lg'}><div className="flex items-start justify-between gap-ui-md"><Skeleton className={compact ? 'h-control-segment w-control-segment' : 'h-control-sm w-control-sm'} /><Skeleton className="h-4 w-14" /></div><div className="mt-ui-lg space-y-ui-sm"><Skeleton className="h-2.5 w-2/3" /><Skeleton className="h-2 w-1/2" /></div>{!compact ? <div className="mt-ui-lg border-t border-border pt-ui-md"><Skeleton className="h-2 w-full" /><Skeleton className="mt-ui-sm h-2 w-4/5" /></div> : null}</Surface>
}

function CardsSkeleton({ compact = false }: { compact?: boolean }) {
  return <div className="grid gap-ui-md md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: compact ? 6 : 3 }).map((_, index) => <CardSkeleton key={index} compact={compact} />)}</div>
}

function ListSkeleton({ count = 6 }: { count?: number }) {
  return <Surface className="overflow-hidden"><div className="flex items-center justify-between border-b border-border px-ui-lg py-ui-md"><Skeleton className="h-2.5 w-28" /><Skeleton className="h-control-xs w-20" /></div><div className="divide-y divide-border">{Array.from({ length: count }).map((_, index) => <div key={index} className="grid min-h-12 gap-ui-md px-ui-lg py-ui-md md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_100px] md:items-center"><div className="space-y-ui-xs"><Skeleton className="h-2.5 w-36" /><Skeleton className="h-2 w-24" /></div><Skeleton className="h-2 w-32" /><Skeleton className="h-4 w-16 md:ml-auto" /></div>)}</div></Surface>
}

function TableSkeleton() {
  return <Surface className="overflow-hidden"><div className="grid grid-cols-4 gap-ui-lg border-b border-border px-ui-lg py-ui-sm">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-2.5" />)}</div>{Array.from({ length: 6 }).map((_, row) => <div key={row} className="grid grid-cols-4 gap-ui-lg border-b border-border/70 px-ui-lg py-ui-md last:border-b-0">{Array.from({ length: 4 }).map((__, cell) => <Skeleton key={cell} className="h-2" />)}</div>)}</Surface>
}

function MetricsSkeleton() {
  return <div className="space-y-ui-md"><div className="grid gap-ui-md sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <Surface key={index} className="p-ui-md"><Skeleton className="h-2 w-20" /><Skeleton className="mt-ui-md h-4 w-24" /><Skeleton className="mt-ui-sm h-2 w-28" /></Surface>)}</div><ListSkeleton count={5} /></div>
}

function PlaygroundSkeleton({ message }: { message: string }) {
  return <Surface className="flex min-h-[28.75rem] w-full flex-col overflow-hidden bg-background"><div className="flex h-workspace-header items-center justify-between border-b border-border bg-surface/70 px-ui-lg"><div className="flex items-center gap-ui-sm"><LoadingMark /><div><p className="font-mono text-system-control font-semibold text-accent-foreground/85">{message}</p><p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Preparing workspace</p></div></div><Skeleton className="h-control-xs w-24" /></div><div className="flex min-h-0 flex-1"><div className="hidden w-playground-rail border-r border-border bg-surface/50 p-ui-sm md:block"><div className="space-y-ui-sm">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-control-sm w-full" />)}</div></div><div className="hidden w-project-sidebar border-r border-border bg-surface/40 p-ui-md lg:block"><div className="space-y-ui-sm">{Array.from({ length: 7 }).map((_, index) => <Skeleton key={index} className={index % 2 ? 'h-2 w-3/4' : 'h-2 w-full'} />)}</div></div><div className="flex min-w-0 flex-1 flex-col p-ui-lg"><div className="mx-auto w-full max-w-conversation flex-1 space-y-ui-md"><Skeleton className="ml-auto h-12 w-2/3" /><Skeleton className="h-20 w-4/5" /><Skeleton className="ml-auto h-10 w-1/2" /></div><Skeleton className="mx-auto mt-ui-lg h-control-row w-full max-w-conversation" /></div><div className="hidden w-inspector border-l border-border bg-surface/40 p-ui-md xl:block"><div className="space-y-ui-sm">{Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className={index % 3 ? 'h-2 w-2/3' : 'h-2 w-full'} />)}</div></div></div></Surface>
}

function AuthSkeleton({ message, description }: { message: string; description?: string }) {
  return <div className="flex min-h-screen items-center justify-center bg-background p-ui-xxl"><Surface className="w-full max-w-sm p-ui-xl"><p className="font-mono text-system-control uppercase tracking-ui-eyebrow text-primary-light">WOOBE / control plane</p><div className="mt-ui-lg flex items-center gap-ui-md"><LoadingMark /><div><p className="font-mono text-system-control font-semibold text-accent-foreground/85">{message}</p>{description ? <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{description}</p> : null}</div></div></Surface></div>
}

function renderLayout(layout: LoadingLayout, message: string) {
  if (layout === 'metrics') return <MetricsSkeleton />
  if (layout === 'compact-cards') return <CardsSkeleton compact />
  if (layout === 'resource-list') return <ListSkeleton count={5} />
  if (layout === 'list') return <ListSkeleton />
  if (layout === 'table') return <TableSkeleton />
  if (layout === 'playground') return <PlaygroundSkeleton message={message} />
  return <CardsSkeleton />
}

export function LoadingState({ message = 'Loading...', description, variant = 'page', layout = 'cards', className, delayMs }: LoadingStateProps) {
  const resolvedDelay = delayMs ?? (variant === 'fullscreen' || variant === 'inline' ? 0 : 120)
  const visible = useDelayedVisible(resolvedDelay)
  if (!visible) return null
  if (variant === 'inline') return <div className={cn('inline-flex items-center gap-ui-sm font-sans text-product-caption text-muted-foreground', className)}><Loader2 className="h-icon w-icon animate-spin text-primary-light" />{message}</div>
  if (variant === 'fullscreen' && layout === 'auth') return <AuthSkeleton message={message} description={description} />
  if (variant === 'fullscreen' && layout === 'playground') return <div className={cn('h-full w-full bg-background p-ui-md', className)}><PlaygroundSkeleton message={message} /></div>
  if (variant === 'panel') return <Surface className={cn('p-ui-md', className)}><div className="mb-ui-md flex items-center gap-ui-sm"><LoadingMark /><div><p className="font-mono text-system-control font-semibold text-accent-foreground/85">{message}</p>{description ? <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{description}</p> : null}</div></div>{renderLayout(layout, message)}</Surface>
  return <div className={cn('w-full space-y-ui-md', className)}><LoadingHeader message={message} description={description} />{renderLayout(layout, message)}</div>
}
