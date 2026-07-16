import type { NetworkAgentBindingSource } from '@/features/network/types'
import { cn } from '@/lib/utils'

const sourceLabel: Record<NetworkAgentBindingSource, string> = {
  draft: 'Draft',
  staging: 'Staging',
  release: 'Release',
}

const sourceTone: Record<NetworkAgentBindingSource, string> = {
  draft: 'border-primary/30 bg-primary/10 text-primary-light',
  staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
  release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
}

const sourceDotTone: Record<NetworkAgentBindingSource, string> = {
  draft: 'bg-primary',
  staging: 'bg-indigo-400',
  release: 'bg-emerald-400',
}

export function networkBindingLabel({
  source,
  version,
  dirty = false,
}: {
  source: NetworkAgentBindingSource
  version?: string | null
  dirty?: boolean
}) {
  const normalizedVersion = version?.trim() || (source === 'draft' ? 'current' : 'pinned')
  return `${sourceLabel[source]} · ${normalizedVersion}${dirty ? ' · unsaved' : ''}`
}

export function NetworkBindingBadge({
  source,
  version,
  dirty = false,
  variant = 'metadata',
  className,
  title,
}: {
  source: NetworkAgentBindingSource
  version?: string | null
  dirty?: boolean
  variant?: 'badge' | 'metadata'
  className?: string
  title?: string
}) {
  const normalizedVersion = version?.trim() || (source === 'draft' ? 'current' : 'pinned')
  const label = networkBindingLabel({ source, version, dirty })

  if (variant === 'metadata') {
    return (
      <span
        title={title ?? label}
        className={cn(
          'inline-flex w-full min-w-0 max-w-full items-center gap-3 border-0 bg-transparent p-0 text-[8px]',
          className,
        )}
        style={{ justifyContent: 'space-between' }}
      >
        <span className={cn(
          'inline-flex min-w-0 items-center gap-1.5 font-medium',
          dirty ? 'text-amber-300' : 'text-slate-400',
        )}>
          <span
            aria-hidden
            className={cn(
              'h-1.5 w-1.5 shrink-0 rounded-full',
              dirty ? 'bg-amber-400' : sourceDotTone[source],
            )}
          />
          <span className="truncate normal-case tracking-normal">
            {sourceLabel[source]}{dirty ? ' · unsaved' : ''}
          </span>
        </span>
        <span className="min-w-0 truncate text-right font-mono text-slate-500">
          {normalizedVersion}
        </span>
      </span>
    )
  }

  return (
    <span
      title={title ?? label}
      className={cn(
        'inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-[8px] font-semibold',
        dirty ? 'border-amber-500/35 bg-amber-500/10 text-amber-200' : sourceTone[source],
        className,
      )}
    >
      <span className="shrink-0 uppercase tracking-wide">{sourceLabel[source]}</span>
      <span aria-hidden className="opacity-60">·</span>
      <span className="truncate font-mono normal-case tracking-normal">{normalizedVersion}</span>
      {dirty ? <span className="shrink-0 normal-case tracking-normal">· unsaved</span> : null}
    </span>
  )
}
