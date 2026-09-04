import { useMemo, useState } from 'react'
import { BrainCircuit, Check, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useContextAssemblers } from '@/features/agents/hooks'
import type { ContextAssemblerDescriptor } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

const LEGACY_DEFAULT_SELECTION = {
  name: 'default',
  version: 'v1',
  strategy_name: 'stdcm',
  strategy_version: 'v1',
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function currentSelection(runtimeConfig: Record<string, unknown>) {
  const raw = recordValue(runtimeConfig.context_assembler)
  const name = typeof raw.name === 'string' && raw.name.trim()
    ? raw.name.trim()
    : LEGACY_DEFAULT_SELECTION.name
  const version = typeof raw.version === 'string' && raw.version.trim()
    ? raw.version.trim()
    : LEGACY_DEFAULT_SELECTION.version
  const strategyName = typeof raw.strategy_name === 'string' && raw.strategy_name.trim()
    ? raw.strategy_name.trim()
    : name === 'default' && version === 'v1'
      ? LEGACY_DEFAULT_SELECTION.strategy_name
      : name
  const strategyVersion = typeof raw.strategy_version === 'string' && raw.strategy_version.trim()
    ? raw.strategy_version.trim()
    : name === 'default' && version === 'v1'
      ? LEGACY_DEFAULT_SELECTION.strategy_version
      : version
  return {
    name,
    version,
    strategy_name: strategyName,
    strategy_version: strategyVersion,
  }
}

function selectionKey(item: Pick<ContextAssemblerDescriptor, 'name' | 'version'>) {
  return `${item.name}:${item.version}`
}

function strategyKey(
  item: Pick<ContextAssemblerDescriptor, 'strategy_name' | 'strategy_version'>,
) {
  return `${item.strategy_name}:${item.strategy_version}`
}

function descriptorIdentity(
  item: Pick<ContextAssemblerDescriptor, 'name' | 'version' | 'strategy_name' | 'strategy_version'>,
) {
  return `${item.name}:${item.version}@${item.strategy_name}:${item.strategy_version}`
}

function DetailList({ items }: { items: string[] }) {
  return (
    <div className="space-y-2.5">
      {items.map((item) => (
        <div key={item} className="flex gap-2.5 text-xs leading-5 text-foreground/80">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
          <span>{item}</span>
        </div>
      ))}
    </div>
  )
}

export function AgentContextAssemblerField() {
  const { state, setField } = useAgentEditor()
  const { data: assemblers = [], isLoading, isError } = useContextAssemblers()
  const selected = useMemo(() => currentSelection(state.runtimeConfig), [state.runtimeConfig])
  const selectedIdentity = descriptorIdentity(selected)
  const selectedFallback = useMemo<ContextAssemblerDescriptor>(() => ({
    name: selected.name,
    version: selected.version,
    strategy_name: selected.strategy_name,
    strategy_version: selected.strategy_version,
    display_name: selected.strategy_name,
    description: '',
    behavior: '',
    recommended_for: [],
    capabilities: [],
    limitations: [],
    configuration: '',
    is_default: false,
    is_system_default_alias: selected.name === 'default',
  }), [selected])

  const exactSelectedDescriptor = assemblers.find(
    (item) => descriptorIdentity(item) === selectedIdentity,
  )
  const selectedStrategyDescriptor = assemblers.find(
    (item) => !item.is_system_default_alias && strategyKey(item) === strategyKey(selected),
  )
  const selectedDescriptor = exactSelectedDescriptor
    ?? (selectedStrategyDescriptor
      ? {
          ...selectedStrategyDescriptor,
          name: selected.name,
          version: selected.version,
          strategy_name: selected.strategy_name,
          strategy_version: selected.strategy_version,
          is_default: false,
          is_system_default_alias: selected.name === 'default',
        }
      : selectedFallback)

  const availableAssemblers = assemblers.length === 0
    ? [selectedFallback]
    : exactSelectedDescriptor
      ? assemblers
      : [selectedDescriptor, ...assemblers]

  const [open, setOpen] = useState(false)
  const [focusedIdentity, setFocusedIdentity] = useState<string | null>(null)

  const focused = availableAssemblers.find(
    (item) => descriptorIdentity(item) === (focusedIdentity || selectedIdentity),
  ) ?? selectedDescriptor

  const catalogReady = !isLoading && !isError && assemblers.length > 0

  const openSelector = () => {
    setFocusedIdentity(selectedIdentity)
    setOpen(true)
  }

  const applySelection = () => {
    if (!focused || !catalogReady) return
    setField('runtimeConfig', {
      ...state.runtimeConfig,
      context_assembler: {
        name: focused.name,
        version: focused.version,
        strategy_name: focused.strategy_name,
        strategy_version: focused.strategy_version,
      },
    })
    setOpen(false)
  }

  return (
    <>
      <section className="rounded-xl border border-border bg-surface p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Context Management</p>
        <p className="mt-1 text-[11px] leading-relaxed text-muted">
          Select the context manager for this Agent snapshot.
        </p>

        <button
          type="button"
          onClick={openSelector}
          className="group mt-3 flex h-12 w-full items-center gap-2.5 rounded-lg border border-border bg-background/40 px-3 text-left transition-colors hover:border-primary/40 hover:bg-accent/35"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary">
            <BrainCircuit className="h-4 w-4" />
          </span>
          <span className="truncate text-sm font-medium text-foreground">{selectedDescriptor.display_name}</span>
          <span className="shrink-0 rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">
            {selectionKey(selectedDescriptor)}
          </span>
          <ChevronRight className="ml-auto h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
        </button>
      </section>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Select a Context Manager"
        className="max-w-5xl overflow-hidden bg-surface/95"
      >
        <div className="grid max-h-[76vh] min-h-[500px] grid-cols-[270px_minmax(0,1fr)] overflow-hidden -m-6">
          <aside className="flex min-h-0 flex-col border-r border-border/90 bg-background/25">
            <div className="border-b border-border/90 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Registered managers</p>
              <p className="mt-1 text-[11px] text-muted">
                {isLoading
                  ? 'Loading registry…'
                  : isError
                    ? 'Current selection'
                    : `${assemblers.length} available`}
              </p>
            </div>

            <div className="min-h-0 flex-1 p-3">
              <ScrollArea className="h-full pr-1">
                <div className="space-y-2">
                  {availableAssemblers.map((item) => {
                    const identity = descriptorIdentity(item)
                    const active = identity === descriptorIdentity(focused)
                    const current = identity === selectedIdentity
                    return (
                      <button
                        key={identity}
                        type="button"
                        onClick={() => setFocusedIdentity(identity)}
                        disabled={!catalogReady && !current}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors disabled:cursor-default',
                          active
                            ? 'border-primary/60 bg-primary/10'
                            : 'border-border/80 bg-background/35 hover:border-primary/30 hover:bg-accent/30',
                        )}
                      >
                        <BrainCircuit className={cn('h-4 w-4 shrink-0', active ? 'text-primary' : 'text-muted')} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-foreground">{item.display_name}</span>
                          <span className="mt-0.5 block truncate text-[9px] text-muted">
                            <span className="font-mono">{selectionKey(item)}</span>
                            <span className="mx-1">·</span>
                            {item.is_system_default_alias ? 'System default' : 'Explicit strategy'}
                          </span>
                        </span>
                        {current ? (
                          <span className="flex items-center gap-1 text-[9px] font-medium uppercase tracking-wide text-primary-light">
                            <Check className="h-3.5 w-3.5" />
                            Selected
                          </span>
                        ) : null}
                      </button>
                    )
                  })}
                </div>
              </ScrollArea>
            </div>
          </aside>

          <section className="flex min-h-0 flex-col">
            <div className="min-h-0 flex-1 p-6">
              <ScrollArea className="h-full pr-2">
                <div className="max-w-3xl pb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
                    <BrainCircuit className="h-4 w-4" />
                  </div>

                  <div className="mt-5 flex flex-wrap items-center gap-2">
                    <h3 className="text-xl font-semibold text-foreground">{focused.display_name}</h3>
                    <span className="rounded border border-border px-2 py-0.5 font-mono text-[10px] text-muted">
                      {selectionKey(focused)}
                    </span>
                    {descriptorIdentity(focused) === selectedIdentity ? (
                      <span className="rounded border border-primary/30 bg-primary/10 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-primary-light">
                        Selected
                      </span>
                    ) : null}
                    {focused.is_default ? (
                      <span className="rounded border border-primary/30 bg-primary/10 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-primary-light">
                        System default
                      </span>
                    ) : null}
                  </div>

                  {catalogReady ? (
                    <>
                      <div className="mt-5">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Description</p>
                        <p className="mt-2 text-sm leading-6 text-foreground/85">{focused.description}</p>
                      </div>

                      <div className="mt-6 border-t border-border/80 pt-5">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">How it operates</p>
                        <p className="mt-2 text-sm leading-6 text-foreground/80">{focused.behavior}</p>
                      </div>

                      <div className="mt-6 grid gap-4 border-t border-border/80 pt-5 sm:grid-cols-[minmax(0,1fr)_220px]">
                        <div>
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Recommended for</p>
                          <div className="mt-3"><DetailList items={focused.recommended_for} /></div>
                        </div>
                        <div className="space-y-3">
                          <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Strategy</p>
                            <p className="mt-2 font-mono text-xs font-medium text-foreground">
                              {focused.strategy_name}:{focused.strategy_version}
                            </p>
                          </div>
                          <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Configuration</p>
                            <p className="mt-2 text-sm font-medium text-foreground">{focused.configuration}</p>
                          </div>
                        </div>
                      </div>

                      <div className="mt-6 grid gap-6 border-t border-border/80 pt-5 md:grid-cols-2">
                        <div>
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Capabilities</p>
                          <div className="mt-3"><DetailList items={focused.capabilities} /></div>
                        </div>
                        <div>
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Limitations</p>
                          <div className="mt-3"><DetailList items={focused.limitations} /></div>
                        </div>
                      </div>

                      <div className="mt-6 rounded-xl border border-border/80 bg-background/35 p-4 text-xs leading-5 text-muted">
                        The selection <span className="font-mono text-foreground">{selectionKey(focused)}</span> and resolved strategy <span className="font-mono text-foreground">{focused.strategy_name}:{focused.strategy_version}</span> are frozen in the Agent snapshot and preserved by immutable releases.
                      </div>
                    </>
                  ) : (
                    <div className="mt-5 rounded-xl border border-border/80 bg-background/35 p-4">
                      <p className="text-sm font-medium text-foreground">
                        {isLoading ? 'Loading manager details…' : 'Manager details are temporarily unavailable.'}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-muted">
                        The current snapshot selection remains visible. Manager-specific metadata is supplied by the backend Registry and rendered here when the catalog is available.
                      </p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>

            <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={applySelection} disabled={!catalogReady}>Select manager</Button>
            </div>
          </section>
        </div>
      </Dialog>
    </>
  )
}
