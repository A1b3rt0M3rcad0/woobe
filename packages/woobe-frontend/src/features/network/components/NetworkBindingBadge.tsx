import { Badge, type BadgeVariant } from '@woobe/ui'
import type { NetworkAgentBindingSource } from '@/features/network/types'
import { cn } from '@/lib/utils'

const sourceLabel: Record<NetworkAgentBindingSource, string> = {
  draft: 'Draft',
  staging: 'Staging',
  release: 'Release',
}

const sourceVariant: Record<NetworkAgentBindingSource, BadgeVariant> = {
  draft: 'default',
  staging: 'network',
  release: 'success',
}

const sourceDotTone: Record<NetworkAgentBindingSource, string> = {
  draft: 'bg-primary',
  staging: 'bg-network',
  release: 'bg-success',
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
        className={cn('inline-flex w-full min-w-0 max-w-full items-center justify-between gap-ui-md font-mono text-system-meta', className)}
      >
        <span className={cn('inline-flex min-w-0 items-center gap-ui-xs font-medium', dirty ? 'text-warning' : 'text-muted-foreground')}>
          <span aria-hidden className={cn('h-1.5 w-1.5 shrink-0 rounded-full', dirty ? 'bg-warning' : sourceDotTone[source])} />
          <span className="truncate">{sourceLabel[source]}{dirty ? ' · unsaved' : ''}</span>
        </span>
        <span className="min-w-0 truncate text-right text-muted-foreground/70">{normalizedVersion}</span>
      </span>
    )
  }

  return (
    <Badge
      title={title ?? label}
      size="compact"
      variant={dirty ? 'warning' : sourceVariant[source]}
      className={cn('min-w-0 max-w-full', className)}
    >
      <span className="shrink-0 uppercase tracking-ui-label">{sourceLabel[source]}</span>
      <span aria-hidden className="opacity-60">·</span>
      <span className="truncate normal-case tracking-normal">{normalizedVersion}</span>
      {dirty ? <span className="shrink-0 normal-case tracking-normal">· unsaved</span> : null}
    </Badge>
  )
}
