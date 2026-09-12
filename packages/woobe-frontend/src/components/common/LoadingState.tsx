import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Skeleton } from '@woobe/ui'
import { cn } from '@/lib/utils'

type LoadingVariant = 'page' | 'workspace' | 'panel' | 'inline' | 'fullscreen'
type LoadingLayout = 'cards' | 'compact-cards' | 'list' | 'resource-list' | 'table' | 'metrics' | 'playground' | 'auth'

interface LoadingStateProps {
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
    if (delayMs <= 0) {
      setVisible(true)
      return undefined
    }
    const timeoutId = window.setTimeout(() => setVisible(true), delayMs)
    return () => window.clearTimeout(timeoutId)
  }, [delayMs])

  return visible
}

function Surface({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('rounded-container border border-border bg-surface/55', className)}>{children}</div>
}

function LoadingMark() {
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
    </span>
  )
}

function LoadingHeader({ message, description }: { message: string; description?: string }) {
  return (
    <Surface className="flex items-center gap-3 px-4 py-3">
      <LoadingMark />
      <div className="min-w-0">
        <p className="font-mono text-[11px] font-semibold text-slate-200">{message}</p>
        {description ? <p className="mt-0.5 font-sans text-xs text-muted">{description}</p> : null}
      </div>
    </Surface>
  )
}

function CardSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <Surface className={compact ? 'p-3' : 'p-4'}>
      <div className="flex items-start justify-between gap-3">
        <Skeleton className={compact ? 'h-7 w-7' : 'h-8 w-8'} />
        <Skeleton className="h-4 w-14" />
      </div>
      <div className="mt-4 space-y-2">
        <Skeleton className="h-2.5 w-2/3" />
        <Skeleton className="h-2 w-1/2" />
      </div>
      {!compact ? (
        <div className="mt-4 border-t border-border pt-3">
          <Skeleton className="h-2 w-full" />
          <Skeleton className="mt-2 h-2 w-4/5" />
        </div>
      ) : null}
    </Surface>
  )
}

function CardsSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: compact ? 6 : 3 }).map((_, index) => <CardSkeleton key={index} compact={compact} />)}
    </div>
  )
}

function ListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <Surface className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <Skeleton className="h-2.5 w-28" />
        <Skeleton className="h-6 w-20" />
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: count }).map((_, index) => (
          <div key={index} className="grid min-h-12 gap-3 px-4 py-3 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_100px] md:items-center">
            <div className="space-y-1.5"><Skeleton className="h-2.5 w-36" /><Skeleton className="h-2 w-24" /></div>
            <Skeleton className="h-2 w-32" />
            <Skeleton className="h-4 w-16 md:ml-auto" />
          </div>
        ))}
      </div>
    </Surface>
  )
}

function TableSkeleton() {
  return (
    <Surface className="overflow-hidden">
      <div className="grid grid-cols-4 gap-4 border-b border-border px-4 py-2.5">
        {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-2.5" />)}
      </div>
      {Array.from({ length: 6 }).map((_, row) => (
        <div key={row} className="grid grid-cols-4 gap-4 border-b border-border/70 px-4 py-3 last:border-b-0">
          {Array.from({ length: 4 }).map((__, cell) => <Skeleton key={cell} className="h-2" />)}
        </div>
      ))}
    </Surface>
  )
}

function MetricsSkeleton() {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Surface key={index} className="p-3">
            <Skeleton className="h-2 w-20" />
            <Skeleton className="mt-3 h-4 w-24" />
            <Skeleton className="mt-2 h-2 w-28" />
          </Surface>
        ))}
      </div>
      <ListSkeleton count={5} />
    </div>
  )
}

function PlaygroundSkeleton({ message }: { message: string }) {
  return (
    <Surface className="flex min-h-[460px] w-full flex-col overflow-hidden bg-background">
      <div className="flex h-[54px] items-center justify-between border-b border-border bg-surface/70 px-4">
        <div className="flex items-center gap-2.5">
          <LoadingMark />
          <div><p className="font-mono text-[11px] font-semibold text-slate-200">{message}</p><p className="mt-0.5 text-[10px] text-muted">Preparing workspace</p></div>
        </div>
        <Skeleton className="h-6 w-24" />
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="hidden w-[52px] border-r border-border bg-surface/50 p-2 md:block">
          <div className="space-y-2">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-8 w-full" />)}</div>
        </div>
        <div className="hidden w-[260px] border-r border-border bg-surface/40 p-3 lg:block">
          <div className="space-y-2">{Array.from({ length: 7 }).map((_, index) => <Skeleton key={index} className={index % 2 ? 'h-2 w-3/4' : 'h-2 w-full'} />)}</div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col p-4">
          <div className="mx-auto w-full max-w-2xl flex-1 space-y-3">
            <Skeleton className="ml-auto h-12 w-2/3" />
            <Skeleton className="h-20 w-4/5" />
            <Skeleton className="ml-auto h-10 w-1/2" />
          </div>
          <Skeleton className="mx-auto mt-4 h-11 w-full max-w-2xl" />
        </div>
        <div className="hidden w-[300px] border-l border-border bg-surface/40 p-3 xl:block">
          <div className="space-y-2">{Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className={index % 3 ? 'h-2 w-2/3' : 'h-2 w-full'} />)}</div>
        </div>
      </div>
    </Surface>
  )
}

function AuthSkeleton({ message, description }: { message: string; description?: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Surface className="w-full max-w-sm p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-primary-light">WOOBE / control plane</p>
        <div className="mt-4 flex items-center gap-3">
          <LoadingMark />
          <div><p className="font-mono text-[11px] font-semibold text-slate-200">{message}</p>{description ? <p className="mt-0.5 text-xs text-muted">{description}</p> : null}</div>
        </div>
      </Surface>
    </div>
  )
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

function getImplicitContext(message: string): { variant: LoadingVariant; layout: LoadingLayout } {
  const path = typeof window !== 'undefined' ? window.location.pathname : ''
  const normalized = message.toLowerCase()
  if (normalized.includes('authentication')) return { variant: 'fullscreen', layout: 'auth' }
  if (path === '/workspaces' || /^\/workspaces\/[^/]+\/projects$/.test(path)) return { variant: 'workspace', layout: 'cards' }
  if (path.includes('/usage')) return { variant: 'page', layout: 'metrics' }
  if (path.includes('/traces')) return { variant: 'page', layout: 'list' }
  return { variant: 'page', layout: 'cards' }
}

export function LoadingState({ message = 'Loading...', description, variant, layout, className, delayMs }: LoadingStateProps) {
  const implicit = getImplicitContext(message)
  const resolvedVariant = variant ?? implicit.variant
  const resolvedLayout = layout ?? implicit.layout
  const resolvedDelay = delayMs ?? (resolvedVariant === 'fullscreen' || resolvedVariant === 'inline' ? 0 : 120)
  const visible = useDelayedVisible(resolvedDelay)

  if (!visible) return null

  if (resolvedVariant === 'inline') {
    return <div className={cn('inline-flex items-center gap-2 font-sans text-xs text-muted', className)}><Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />{message}</div>
  }
  if (resolvedVariant === 'fullscreen' && resolvedLayout === 'auth') return <AuthSkeleton message={message} description={description} />
  if (resolvedVariant === 'fullscreen' && resolvedLayout === 'playground') return <div className={cn('h-full w-full bg-background p-3', className)}><PlaygroundSkeleton message={message} /></div>
  if (resolvedVariant === 'panel') {
    return <Surface className={cn('p-3', className)}><div className="mb-3 flex items-center gap-2.5"><LoadingMark /><div><p className="font-mono text-[11px] font-semibold text-slate-200">{message}</p>{description ? <p className="mt-0.5 text-xs text-muted">{description}</p> : null}</div></div>{renderLayout(resolvedLayout, message)}</Surface>
  }

  return <div className={cn('w-full space-y-3', className)}><LoadingHeader message={message} description={description} />{renderLayout(resolvedLayout, message)}</div>
}
