import { useMemo, useState } from 'react'
import { Check, Route, Settings2 } from 'lucide-react'
import {
  Badge,
  Button,
  Dialog,
  DialogFooter,
  EmptyStatePanel,
  ScrollArea,
  TechnicalListItem,
} from '@woobe/ui'

import {
  executionStrategyDescriptor,
  executionStrategyFromRuntimeConfig,
  withExecutionStrategy,
} from '@/features/agents/executionStrategy'
import { useExecutionStrategies } from '@/features/agents/hooks'
import type { ExecutionStrategyDescriptor } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

function DetailList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="font-sans text-product-caption text-muted-foreground">No metadata available.</p>
  }

  return (
    <div className="space-y-ui-sm">
      {items.map((item) => (
        <div key={item} className="flex gap-ui-sm font-sans text-product-small text-slate-300">
          <span className="mt-[0.4rem] h-1 w-1 shrink-0 rounded-full bg-primary" />
          <span>{item}</span>
        </div>
      ))}
    </div>
  )
}

export function AgentExecutionStrategyField({
  readOnly = false,
  compact = false,
}: {
  readOnly?: boolean
  compact?: boolean
}) {
  const { state, setField } = useAgentEditor()
  const { data: strategies = [], isLoading, isError } = useExecutionStrategies()
  const selected = executionStrategyFromRuntimeConfig(state.runtimeConfig)
  const selectedDescriptor = executionStrategyDescriptor(strategies, selected)

  const selectedFallback = useMemo<ExecutionStrategyDescriptor>(() => ({
    name: selected,
    display_name: selected,
    description: '',
    behavior: '',
    recommended_for: [],
    capabilities: [],
    limitations: [],
    is_default: false,
  }), [selected])

  const availableStrategies = selectedDescriptor
    ? strategies
    : [selectedFallback, ...strategies]

  const [open, setOpen] = useState(false)
  const [focusedName, setFocusedName] = useState<string | null>(null)
  const focusedNameResolved = focusedName || selected
  const focusedDescriptor = executionStrategyDescriptor(availableStrategies, focusedNameResolved) ?? selectedFallback
  const focusedIsCurrent = focusedDescriptor.name === selected
  const focusedCatalogBacked = strategies.some((strategy) => strategy.name === focusedDescriptor.name)
  const catalogReady = !isLoading && !isError && strategies.length > 0
  const canApplySelection = !readOnly && catalogReady && focusedCatalogBacked && !focusedIsCurrent
  const currentDescriptor = selectedDescriptor ?? selectedFallback

  const openSelector = () => {
    setFocusedName(selected)
    setOpen(true)
  }

  const applySelection = () => {
    if (!canApplySelection) return
    setField('runtimeConfig', withExecutionStrategy(state.runtimeConfig, focusedDescriptor.name))
    setOpen(false)
  }

  return (
    <>
      <section className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')} aria-label="Execution Strategy">
        <div>
          <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Execution Strategy</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Selects the backend-registered execution algorithm used by this Agent.</p>
        </div>

        <div className="mt-ui-md">
          <TechnicalListItem
            label={currentDescriptor.display_name}
            description={currentDescriptor.description || (isLoading ? 'Loading registered execution strategy…' : isError ? 'Strategy catalog unavailable.' : 'Strategy metadata unavailable.')}
            density="compact"
            leading={(
              <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-primary/20 bg-primary/10 text-primary-light">
                <Route className="h-icon w-icon" />
              </span>
            )}
            meta={(
              <>
                <Badge variant="outline" size="compact">{selected}</Badge>
                {currentDescriptor.is_default ? <Badge variant="success" size="compact">Default</Badge> : null}
                {readOnly ? <Badge variant="outline" size="compact">Snapshot</Badge> : null}
              </>
            )}
            trailing={(
              <Button type="button" size="sm" variant="outline" onClick={openSelector}>
                <Settings2 className="h-icon-sm w-icon-sm" />
                {readOnly ? 'View details' : 'Change'}
              </Button>
            )}
          />
        </div>
      </section>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Select Execution Strategy"
        variant="workspace"
        height="workspace"
      >
        <div className="grid h-full min-h-0 grid-cols-[15.625rem_minmax(0,1fr)] overflow-hidden">
          <aside className="flex min-h-0 flex-col border-r border-border bg-background/25">
            <div className="shrink-0 border-b border-border px-ui-lg py-ui-md">
              <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Registered strategies</p>
              <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
                {isLoading ? 'Loading catalog…' : isError ? 'Current selection only' : `${strategies.length} available`}
              </p>
            </div>

            <ScrollArea className="min-h-0 flex-1 p-ui-md pr-ui-sm">
              <div className="space-y-ui-sm">
                {availableStrategies.map((strategy) => {
                  const active = strategy.name === focusedDescriptor.name
                  const current = strategy.name === selected
                  const catalogBacked = strategies.some((item) => item.name === strategy.name)
                  return (
                    <TechnicalListItem
                      key={strategy.name}
                      selected={active}
                      disabled={!catalogBacked && !current}
                      onClick={() => setFocusedName(strategy.name)}
                      leading={<Route className="h-icon w-icon text-primary-light" />}
                      label={strategy.display_name}
                      description={strategy.name}
                      meta={strategy.is_default ? 'System default' : undefined}
                      trailing={current ? <span className="flex items-center gap-ui-xs font-mono text-system-meta uppercase text-primary-light"><Check className="h-icon-sm w-icon-sm" />Selected</span> : null}
                    />
                  )
                })}
              </div>
            </ScrollArea>
          </aside>

          <section className="flex min-h-0 min-w-0 flex-col">
            <ScrollArea className="min-h-0 flex-1 px-ui-xl py-ui-lg pr-ui-md">
              <div className="mx-auto max-w-dialog-content pb-ui-sm">
                <div className="flex items-start gap-ui-md">
                  <div className="flex h-control w-control shrink-0 items-center justify-center rounded-control border border-primary/20 bg-primary/10 text-primary-light">
                    <Route className="h-icon-lg w-icon-lg" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-ui-sm">
                      <h3 className="font-mono text-system-heading font-semibold text-slate-50">{focusedDescriptor.display_name}</h3>
                      <Badge variant="outline" size="compact">{focusedDescriptor.name}</Badge>
                      {focusedIsCurrent ? <Badge variant="success" size="compact">Selected</Badge> : null}
                      {focusedDescriptor.is_default ? <Badge variant="outline" size="compact">System default</Badge> : null}
                    </div>
                    <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
                      {focusedCatalogBacked ? 'Backend-registered execution strategy.' : 'Snapshot selection not present in the active backend catalog.'}
                    </p>
                  </div>
                </div>

                {catalogReady && focusedCatalogBacked ? (
                  <>
                    <div className="mt-ui-lg grid gap-ui-lg border-t border-border/75 pt-ui-lg md:grid-cols-2">
                      <div>
                        <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Description</p>
                        <p className="mt-ui-sm font-sans text-product-body text-slate-200">{focusedDescriptor.description}</p>
                      </div>
                      <div>
                        <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">How it operates</p>
                        <p className="mt-ui-sm font-sans text-product-body text-slate-300">{focusedDescriptor.behavior}</p>
                      </div>
                    </div>

                    <div className="mt-ui-lg border-t border-border/75 pt-ui-lg">
                      <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Recommended for</p>
                      <div className="mt-ui-sm"><DetailList items={focusedDescriptor.recommended_for} /></div>
                    </div>

                    <div className="mt-ui-lg grid gap-ui-xl border-t border-border/75 pt-ui-lg md:grid-cols-2">
                      <div>
                        <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Capabilities</p>
                        <div className="mt-ui-sm"><DetailList items={focusedDescriptor.capabilities} /></div>
                      </div>
                      <div>
                        <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Limitations</p>
                        <div className="mt-ui-sm"><DetailList items={focusedDescriptor.limitations} /></div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="mt-ui-lg">
                    <EmptyStatePanel
                      compact
                      title={isLoading ? 'Loading strategy details…' : 'Strategy details unavailable'}
                      description="The current snapshot selection remains visible. Backend registry metadata appears when the catalog is available."
                    />
                  </div>
                )}
              </div>
            </ScrollArea>

            <DialogFooter
              meta={(
                <p className="font-sans text-product-caption text-muted-foreground">
                  {focusedCatalogBacked ? `${focusedDescriptor.name}${focusedDescriptor.is_default ? ' · system default' : ''}` : 'Backend registry metadata unavailable'}
                </p>
              )}
              actions={(
                <>
                  <Button variant="outline" onClick={() => setOpen(false)}>{readOnly ? 'Close' : 'Cancel'}</Button>
                  {!readOnly ? <Button onClick={applySelection} disabled={!canApplySelection}>{focusedIsCurrent ? 'Selected' : 'Use strategy'}</Button> : null}
                </>
              )}
            />
          </section>
        </div>
      </Dialog>
    </>
  )
}
