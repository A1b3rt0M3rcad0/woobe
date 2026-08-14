import { useEffect, useState, type ReactNode } from 'react'
import { Loader2, Play } from 'lucide-react'
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

function SkeletonLine({ className }: { className?: string }) {
  return <div className={cn('h-2.5 animate-pulse rounded-full bg-white/[0.07]', className)} />
}

function SkeletonBox({ className, children }: { className?: string; children?: ReactNode }) {
  return (
    <div className={cn('animate-pulse rounded-xl border border-border/70 bg-surface/60', className)}>
      {children}
    </div>
  )
}

function LoadingMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn(
      'relative flex shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light shadow-sm shadow-primary/10',
      compact ? 'h-8 w-8' : 'h-10 w-10',
    )}>
      <div className="absolute inset-0 rounded-xl bg-primary/10 blur-md" />
      <Loader2 className={cn('relative animate-spin', compact ? 'h-4 w-4' : 'h-5 w-5')} />
    </div>
  )
}

function LoadingHeader({ message, description }: { message: string; description?: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/60 p-4 shadow-lg shadow-black/5">
      <div className="flex items-center gap-3">
        <LoadingMark />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-white">{message}</p>
          <p className="mt-1 text-xs leading-5 text-muted">{description || 'Preparing the workspace view.'}</p>
        </div>
      </div>
    </div>
  )
}

function CardsSkeleton({ count = 3, tall = false }: { count?: number; tall?: boolean }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <SkeletonBox key={index} className={cn('p-6', tall ? 'min-h-[260px]' : 'min-h-[240px]')}>
          <div className="flex items-start justify-between gap-3">
            <div className="h-12 w-12 rounded-xl bg-white/[0.07]" />
            <div className="h-6 w-20 rounded-full bg-white/[0.06]" />
          </div>
          <div className="mt-6 space-y-3">
            <SkeletonLine className="h-3 w-2/3" />
            <SkeletonLine className="h-2.5 w-1/2" />
          </div>
          <div className="my-5 h-px bg-border/70" />
          <div className="space-y-2">
            <SkeletonLine className="w-full" />
            <SkeletonLine className="w-4/5" />
          </div>
          <div className="mt-8 flex justify-between">
            <SkeletonLine className="w-24" />
            <div className="h-4 w-4 rounded bg-white/[0.06]" />
          </div>
        </SkeletonBox>
      ))}
    </div>
  )
}

function CompactCardsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <SkeletonBox key={index} className="p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <div className="h-10 w-10 shrink-0 rounded-xl bg-white/[0.07]" />
              <div className="min-w-0 flex-1 space-y-2">
                <SkeletonLine className="h-3 w-2/3" />
                <SkeletonLine className="w-1/2" />
              </div>
            </div>
            <div className="h-4 w-4 rounded bg-white/[0.06]" />
          </div>
          <div className="mt-4 flex gap-2">
            <div className="h-5 w-20 rounded-full bg-white/[0.06]" />
            <div className="h-5 w-16 rounded-full bg-white/[0.06]" />
          </div>
          <SkeletonLine className="mt-4 w-32" />
        </SkeletonBox>
      ))}
    </div>
  )
}

function ListSkeleton({ count = 7 }: { count?: number }) {
  return (
    <SkeletonBox className="overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <SkeletonLine className="h-3 w-32" />
        <SkeletonLine className="mt-2 w-52" />
      </div>
      <div className="divide-y divide-border/80">
        {Array.from({ length: count }).map((_, index) => (
          <div key={index} className="grid gap-4 px-5 py-4 md:grid-cols-[1.3fr_1fr_120px_120px_160px] md:items-center">
            <div className="space-y-2">
              <SkeletonLine className="h-3 w-28" />
              <SkeletonLine className="w-40" />
            </div>
            <div className="space-y-2">
              <SkeletonLine className="h-3 w-36" />
              <SkeletonLine className="w-24" />
            </div>
            <SkeletonLine className="h-6 w-20" />
            <div className="space-y-2">
              <SkeletonLine className="w-14" />
              <SkeletonLine className="h-3 w-20" />
            </div>
            <div className="space-y-2 md:ml-auto md:w-32">
              <SkeletonLine />
              <SkeletonLine className="w-24 md:ml-auto" />
            </div>
          </div>
        ))}
      </div>
    </SkeletonBox>
  )
}

function MetricsSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <SkeletonBox key={index} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-3">
                <SkeletonLine className="w-24" />
                <SkeletonLine className="h-5 w-28" />
                <SkeletonLine className="w-36" />
              </div>
              <div className="h-10 w-10 rounded-xl bg-white/[0.07]" />
            </div>
          </SkeletonBox>
        ))}
      </div>
      <SkeletonBox className="p-5">
        <SkeletonLine className="h-3 w-40" />
        <div className="mt-5 space-y-3">
          {Array.from({ length: 7 }).map((_, index) => (
            <div key={index} className="grid gap-3 md:grid-cols-[120px_minmax(0,1fr)_96px] md:items-center">
              <SkeletonLine className="w-20" />
              <SkeletonLine className="h-2 w-full" />
              <SkeletonLine className="w-14 md:ml-auto" />
            </div>
          ))}
        </div>
      </SkeletonBox>
    </div>
  )
}

function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <SkeletonBox className="overflow-hidden">
      <div className="grid grid-cols-4 gap-4 border-b border-border px-5 py-4">
        {Array.from({ length: 4 }).map((_, index) => <SkeletonLine key={index} className="h-3" />)}
      </div>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="grid grid-cols-4 gap-4 border-b border-border/70 px-5 py-4 last:border-b-0">
          {Array.from({ length: 4 }).map((__, cellIndex) => <SkeletonLine key={cellIndex} />)}
        </div>
      ))}
    </SkeletonBox>
  )
}

function PlaygroundSkeleton({ message }: { message: string }) {
  return (
    <div className="flex min-h-[520px] w-full flex-col overflow-hidden rounded-xl border border-border/80 bg-background">
      <div className="flex h-14 items-center justify-between border-b border-border bg-surface/70 px-4">
        <div className="flex items-center gap-3">
          <LoadingMark compact />
          <div>
            <p className="text-sm font-semibold text-white">{message}</p>
            <p className="mt-0.5 text-xs text-muted">Preparing the agent workspace.</p>
          </div>
        </div>
        <SkeletonLine className="h-7 w-28" />
      </div>
      <div className="flex flex-1 min-h-0">
        <div className="hidden w-12 border-r border-border bg-surface/40 p-2 md:block">
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-8 rounded-lg bg-white/[0.06]" />)}
          </div>
        </div>
        <div className="hidden w-64 border-r border-border bg-surface/40 p-4 lg:block">
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, index) => <SkeletonLine key={index} className={index % 2 === 0 ? 'w-full' : 'w-3/4'} />)}
          </div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col p-5">
          <div className="mx-auto w-full max-w-2xl flex-1 space-y-4">
            <SkeletonBox className="ml-auto h-16 w-2/3" />
            <SkeletonBox className="h-24 w-4/5" />
            <SkeletonBox className="ml-auto h-14 w-1/2" />
          </div>
          <SkeletonBox className="mx-auto mt-5 h-12 w-full max-w-2xl" />
        </div>
        <div className="hidden w-80 border-l border-border bg-surface/40 p-4 xl:block">
          <div className="space-y-3">
            <SkeletonLine className="h-3 w-28" />
            {Array.from({ length: 8 }).map((_, index) => <SkeletonLine key={index} className={index % 3 === 0 ? 'w-full' : 'w-2/3'} />)}
          </div>
        </div>
      </div>
    </div>
  )
}

function AuthSkeleton({ message, description }: { message: string; description?: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-sm rounded-2xl border border-border/80 bg-surface/70 p-6 text-center shadow-2xl shadow-black/20">
        <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-white">
          <Play className="h-5 w-5" />
        </div>
        <p className="mt-5 text-sm font-semibold text-white">ProjectRAI</p>
        <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
          {message}
        </div>
        {description && <p className="mt-2 text-xs leading-5 text-muted">{description}</p>}
      </div>
    </div>
  )
}

function renderLayout(layout: LoadingLayout, variant: LoadingVariant, message: string) {
  if (layout === 'metrics') return <MetricsSkeleton />
  if (layout === 'compact-cards') return <CompactCardsSkeleton />
  if (layout === 'resource-list') return <ListSkeleton count={5} />
  if (layout === 'list') return <ListSkeleton />
  if (layout === 'table') return <TableSkeleton />
  if (layout === 'playground') return <PlaygroundSkeleton message={message} />
  return <CardsSkeleton tall={variant === 'workspace'} />
}

function getImplicitContext(message: string): { variant: LoadingVariant; layout: LoadingLayout } {
  const isBrowser = typeof window !== 'undefined'
  const path = isBrowser ? window.location.pathname : ''
  const normalizedMessage = message.toLowerCase()

  if (normalizedMessage.includes('authentication')) return { variant: 'fullscreen', layout: 'auth' }
  if (path === '/workspaces' || /^\/workspaces\/[^/]+\/projects$/.test(path)) return { variant: 'workspace', layout: 'cards' }
  if (path.includes('/usage')) return { variant: 'page', layout: 'metrics' }
  if (path.includes('/traces')) return { variant: 'page', layout: 'list' }

  return { variant: 'page', layout: 'cards' }
}

export function LoadingState({
  message = 'Loading...',
  description,
  variant,
  layout,
  className,
  delayMs,
}: LoadingStateProps) {
  const implicit = getImplicitContext(message)
  const resolvedVariant = variant ?? implicit.variant
  const resolvedLayout = layout ?? implicit.layout
  const resolvedDelay = delayMs ?? (resolvedVariant === 'fullscreen' || resolvedVariant === 'inline' ? 0 : 120)
  const visible = useDelayedVisible(resolvedDelay)

  if (!visible) return null

  if (resolvedVariant === 'inline') {
    return (
      <div className={cn('inline-flex items-center gap-2 text-sm text-muted', className)}>
        <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
        <span>{message}</span>
      </div>
    )
  }

  if (resolvedVariant === 'fullscreen' && resolvedLayout === 'auth') {
    return <AuthSkeleton message={message} description={description} />
  }

  if (resolvedVariant === 'fullscreen' && resolvedLayout === 'playground') {
    return (
      <div className={cn('h-full w-full bg-background p-4', className)}>
        <PlaygroundSkeleton message={message} />
      </div>
    )
  }

  if (resolvedVariant === 'panel') {
    return (
      <div className={cn('rounded-xl border border-border/80 bg-surface/60 p-4', className)}>
        <div className="mb-4 flex items-center gap-3">
          <LoadingMark compact />
          <div>
            <p className="text-sm font-medium text-white">{message}</p>
            {description && <p className="mt-1 text-xs text-muted">{description}</p>}
          </div>
        </div>
        {resolvedLayout === 'list' ? <ListSkeleton count={3} /> : <CardsSkeleton count={2} />}
      </div>
    )
  }

  return (
    <div className={cn('w-full space-y-5', className)}>
      <LoadingHeader message={message} description={description} />
      {renderLayout(resolvedLayout, resolvedVariant, message)}
    </div>
  )
}
