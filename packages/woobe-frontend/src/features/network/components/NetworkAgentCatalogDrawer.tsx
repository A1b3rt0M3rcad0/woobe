import { useMemo, useState } from 'react'
import { Bot, Check, Plus, Search, X } from 'lucide-react'
import { Badge, Button, EmptyStatePanel, Input, TechnicalListItem } from '@woobe/ui'
import type { Agent } from '@/features/agents/types'

export type NetworkAgentCatalogMode = 'first-agent' | 'add-specialist'

export function NetworkAgentCatalogDrawer({
  open,
  mode = 'add-specialist',
  agents,
  addedAgentIds,
  onClose,
  onAdd,
  onCreate,
}: {
  open: boolean
  mode?: NetworkAgentCatalogMode
  agents: Agent[]
  addedAgentIds: Set<string>
  onClose: () => void
  onAdd: (agent: Agent) => void
  onCreate: () => void
}) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    const matched = !term
      ? agents
      : agents.filter((agent) => `${agent.name} ${agent.description ?? ''} ${agent.provider} ${agent.model}`.toLowerCase().includes(term))
    return [...matched].sort((left, right) => {
      const leftReady = left.status?.toLowerCase() === 'active' ? 0 : 1
      const rightReady = right.status?.toLowerCase() === 'active' ? 0 : 1
      return leftReady - rightReady || left.name.localeCompare(right.name)
    })
  }, [agents, query])
  if (!open) return null

  const firstAgent = mode === 'first-agent'
  const title = firstAgent ? 'Choose entry Agent' : 'Add specialist'
  const description = firstAgent
    ? 'This Agent receives Network requests and becomes the entry point automatically.'
    : 'Add an Agent to the composition, then connect the delegation path on the Canvas.'

  return (
    <div className="absolute inset-0 z-popover bg-background/75 backdrop-blur-sm" onMouseDown={onClose}>
      <aside className="flex h-full w-full max-w-dialog-compact flex-col border-r border-border bg-surface" onMouseDown={(event) => event.stopPropagation()} aria-label={title}>
        <header className="flex h-dialog-header shrink-0 items-center gap-ui-md border-b border-border px-ui-lg">
          <div className="min-w-0 flex-1">
            <h2 className="font-mono text-system-heading font-semibold text-accent-foreground">{title}</h2>
            <p className="mt-ui-xs truncate font-sans text-product-caption text-muted-foreground">{description}</p>
          </div>
          <Button type="button" variant="ghost" size="iconSm" onClick={onClose} aria-label="Close Agent catalog"><X className="h-icon w-icon" /></Button>
        </header>

        <div className="space-y-ui-sm border-b border-border p-ui-md">
          <Button type="button" variant="outline" className="w-full" onClick={onCreate}>
            <Plus className="mr-ui-xs h-icon-sm w-icon-sm" />
            {firstAgent ? 'Create entry Agent' : 'Create and add specialist'}
          </Button>
          <div className="relative">
            <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
            <Input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, model or provider" className="pl-9" />
          </div>
        </div>

        <div className="scrollbar-thin min-h-0 flex-1 space-y-ui-sm overflow-y-auto overscroll-contain p-ui-md">
          {filtered.map((agent) => {
            const added = addedAgentIds.has(agent.id)
            const inactive = agent.status?.toLowerCase() !== 'active'
            const disabled = added || inactive
            const actionLabel = added ? 'Already in Network' : inactive ? 'Agent unavailable' : firstAgent ? 'Use as entry Agent' : 'Add specialist'
            return (
              <TechnicalListItem
                key={agent.id}
                leading={<Bot className="h-icon w-icon text-primary-light" />}
                label={agent.name}
                description={`${agent.provider}/${agent.model}`}
                meta={agent.description || 'No description'}
                trailing={(
                  <div className="flex flex-col items-end gap-ui-xs">
                    <Badge size="compact" variant={inactive ? 'warning' : 'success'}>{inactive ? 'Unavailable' : 'Ready'}</Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant={added ? 'ghost' : inactive ? 'outline' : 'default'}
                      disabled={disabled}
                      title={inactive ? 'Activate the Agent before using it in a Network Draft.' : undefined}
                      onClick={() => onAdd(agent)}
                    >
                      {added ? <Check className="mr-ui-xs h-icon-sm w-icon-sm" /> : <Plus className="mr-ui-xs h-icon-sm w-icon-sm" />}
                      {actionLabel}
                    </Button>
                  </div>
                )}
                className={added ? 'border-primary/25 bg-primary/[0.04]' : undefined}
              />
            )
          })}
          {!filtered.length ? <EmptyStatePanel compact title="No Agents match this search" /> : null}
        </div>
      </aside>
    </div>
  )
}
