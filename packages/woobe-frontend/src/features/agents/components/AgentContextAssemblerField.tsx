import { skillsConfig } from '@/features/skills/config'
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

type ContextManagerOption = {
  strategyKey: string
  descriptor: ContextAssemblerDescriptor
  selectionDescriptor: ContextAssemblerDescriptor
  isSystemDefault: boolean
  catalogBacked: boolean
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

function DetailList({ items }: { items: string[] }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item} className="flex gap-2 text-[12px] leading-[1.45rem] text-foreground/80">
          <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-primary" />
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
  const selectedStrategyKey = strategyKey(selected)

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
    is_default: selected.name === 'default',
    is_system_default_alias: selected.name === 'default',
  }), [selected])

  const catalogOptions = useMemo<ContextManagerOption[]>(() => {
    const groups = new Map<string, ContextAssemblerDescriptor[]>()

    for (const item of assemblers) {
      const key = strategyKey(item)
      const group = groups.get(key)
      if (group) group.push(item)
      else groups.set(key, [item])
    }

    return Array.from(groups.entries())
      .map(([key, entries]) => {
        const strategyDescriptor = entries.find((item) => !item.is_system_default_alias)
          ?? entries[0]
        const defaultAlias = entries.find((item) => item.is_default && item.is_system_default_alias)
          ?? entries.find((item) => item.is_system_default_alias)

        return {
          strategyKey: key,
          descriptor: strategyDescriptor,
          selectionDescriptor: defaultAlias ?? strategyDescriptor,
          isSystemDefault: Boolean(defaultAlias?.is_default),
          catalogBacked: true,
        }
      })
      .sort((left, right) => {
        if (left.isSystemDefault !== right.isSystemDefault) {
          return left.isSystemDefault ? -1 : 1
        }
        return left.descriptor.display_name.localeCompare(right.descriptor.display_name)
      })
  }, [assemblers])

  const selectedCatalogOption = catalogOptions.find(
    (option) => option.strategyKey === selectedStrategyKey,
  )
  const selectedDescriptor = selectedCatalogOption?.descriptor ?? selectedFallback

  const selectedFallbackOption = useMemo<ContextManagerOption>(() => ({
    strategyKey: selectedStrategyKey,
    descriptor: selectedFallback,
    selectionDescriptor: selectedFallback,
    isSystemDefault: selected.name === 'default',
    catalogBacked: false,
  }), [selected.name, selectedFallback, selectedStrategyKey])

  const availableOptions = selectedCatalogOption
    ? catalogOptions
    : [selectedFallbackOption, ...catalogOptions]

  const [open, setOpen] = useState(false)
  const [focusedStrategyKey, setFocusedStrategyKey] = useState<string | null>(null)

  const focused = availableOptions.find(
    (option) => option.strategyKey === (focusedStrategyKey || selectedStrategyKey),
  ) ?? selectedFallbackOption
  const focusedDescriptor = focused.descriptor
  const focusedIsCurrent = focused.strategyKey === selectedStrategyKey
  const focusedSelectionKey = focusedIsCurrent
    ? selectionKey(selected)
    : selectionKey(focused.selectionDescriptor)
  const catalogReady = !isLoading && !isError && assemblers.length > 0
  const incompatibleSkills = skillsConfig(state.runtimeConfig).bindings.some(item => item.enabled) && !focusedDescriptor.supports_skills
  const canApplySelection = catalogReady && focused.catalogBacked && !focusedIsCurrent && !incompatibleSkills

  const openSelector = () => {
    setFocusedStrategyKey(selectedStrategyKey)
    setOpen(true)
  }

  const applySelection = () => {
    if (!canApplySelection) return
    const next = focused.selectionDescriptor
    setField('runtimeConfig', {
      ...state.runtimeConfig,
      context_assembler: {
        name: next.name,
        version: next.version,
        strategy_name: next.strategy_name,
        strategy_version: next.strategy_version,
      },
    })
    setOpen(false)
  }

  return (
    <>
      <section>
        <button
          type="button"
          onClick={openSelector}
          aria-label={`Change context manager. Current selection: ${selectedDescriptor.display_name}`}
          className="group flex min-h-16 w-full items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-left transition-colors hover:border-primary/40 hover:bg-accent/20"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background/40 text-primary">
            <BrainCircuit className="h-4 w-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted">
              Selected context manager
            </span>
            <span className="mt-0.5 block truncate text-sm font-semibold text-foreground">
              {selectedDescriptor.display_name}
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium text-primary-light">
            Change
            <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </span>
        </button>
      </section>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Select a Context Manager"
        className="max-w-[1080px] overflow-hidden bg-surface/95"
        contentClassName="p-0"
      >
        <div className="grid h-[min(640px,calc(100svh-7rem))] min-h-0 grid-cols-[250px_minmax(0,1fr)] overflow-hidden">
          <aside className="flex min-h-0 flex-col border-r border-border/90 bg-background/25">
            <div className="shrink-0 border-b border-border/90 px-4 py-3.5">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">Registered managers</p>
              <p className="mt-1 text-[10px] text-muted">
                {isLoading
                  ? 'Loading registry…'
                  : isError
                    ? 'Current selection only'
                    : `${catalogOptions.length} available`}
              </p>
            </div>

            <ScrollArea className="min-h-0 flex-1 p-3 pr-2">
              <div className="space-y-1.5">
                {availableOptions.map((option) => {
                  const active = option.strategyKey === focused.strategyKey
                  const current = option.strategyKey === selectedStrategyKey
                  const item = option.descriptor
                  return (
                    <button
                      key={option.strategyKey}
                      type="button"
                      onClick={() => setFocusedStrategyKey(option.strategyKey)}
                      disabled={!option.catalogBacked && !current}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-lg border px-2.5 py-2.5 text-left transition-colors disabled:cursor-default',
                        active
                          ? 'border-primary/60 bg-primary/10'
                          : 'border-border/75 bg-background/30 hover:border-primary/30 hover:bg-accent/25',
                      )}
                    >
                      <BrainCircuit className={cn('h-3.5 w-3.5 shrink-0', active ? 'text-primary' : 'text-muted')} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-medium leading-5 text-foreground">{item.display_name}</span>
                        <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[9px] leading-4 text-muted">
                          <span className="truncate font-mono">{option.strategyKey}</span>
                          {option.isSystemDefault ? (
                            <>
                              <span className="text-border">·</span>
                              <span className="shrink-0">System default</span>
                            </>
                          ) : null}
                        </span>
                      </span>
                      {current ? (
                        <span className="flex shrink-0 items-center gap-1 text-[8px] font-semibold uppercase tracking-wide text-primary-light">
                          <Check className="h-3 w-3" />
                          Selected
                        </span>
                      ) : null}
                    </button>
                  )
                })}
              </div>
            </ScrollArea>
          </aside>

          <section className="flex min-h-0 min-w-0 flex-col">
            <ScrollArea className="min-h-0 flex-1 px-5 py-4 pr-3">
              <div className="mx-auto max-w-[760px] pb-2">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light">
                    <BrainCircuit className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <h3 className="text-lg font-semibold leading-7 text-foreground">{focusedDescriptor.display_name}</h3>
                      <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted">
                        {focused.strategyKey}
                      </span>
                      {focusedIsCurrent ? (
                        <span className="rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider text-primary-light">
                          Selected
                        </span>
                      ) : null}
                      {focused.isSystemDefault ? (
                        <span className="rounded border border-border bg-background/40 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider text-muted">
                          System default
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-[10px] text-muted">
                      {focusedIsCurrent && selected.name !== 'default'
                        ? 'Explicit strategy selection'
                        : focused.isSystemDefault
                          ? 'System default strategy'
                          : 'Registered strategy'}
                    </p>
                  </div>
                </div>

                {catalogReady && focused.catalogBacked ? (
                  <>
                    <div className="mt-4 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-lg border border-border/75 bg-background/30 px-3 py-2.5">
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Selection</p>
                        <p className="mt-1 truncate font-mono text-[11px] font-medium text-foreground">{focusedSelectionKey}</p>
                      </div>
                      <div className="rounded-lg border border-border/75 bg-background/30 px-3 py-2.5">
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Resolved strategy</p>
                        <p className="mt-1 truncate font-mono text-[11px] font-medium text-foreground">{focused.strategyKey}</p>
                      </div>
                      <div className="rounded-lg border border-border/75 bg-background/30 px-3 py-2.5">
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Configuration</p>
                        <p className="mt-1 truncate text-[11px] font-medium text-foreground">{focusedDescriptor.configuration}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 border-t border-border/75 pt-4 md:grid-cols-2">
                      <div>
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Description</p>
                        <p className="mt-1.5 text-[13px] leading-5 text-foreground/85">{focusedDescriptor.description}</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">How it operates</p>
                        <p className="mt-1.5 text-[13px] leading-5 text-foreground/80">{focusedDescriptor.behavior}</p>
                      </div>
                    </div>

                    <div className="mt-4 border-t border-border/75 pt-4">
                      <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Recommended for</p>
                      <div className="mt-2 grid gap-x-5 gap-y-1 sm:grid-cols-2">
                        <DetailList items={focusedDescriptor.recommended_for} />
                      </div>
                    </div>

                    <div className="mt-4 grid gap-5 border-t border-border/75 pt-4 md:grid-cols-2">
                      <div>
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Capabilities</p>
                        <div className="mt-2"><DetailList items={focusedDescriptor.capabilities} /></div>
                      </div>
                      <div>
                        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Limitations</p>
                        <div className="mt-2"><DetailList items={focusedDescriptor.limitations} /></div>
                      </div>
                    </div>

                    <div className="mt-4 rounded-lg border border-border/75 bg-background/30 px-3.5 py-3 text-[11px] leading-5 text-muted">
                      Selecting <span className="font-mono text-foreground">{selectionKey(focused.selectionDescriptor)}</span> freezes the resolved strategy <span className="font-mono text-foreground">{focused.strategyKey}</span> in the Agent snapshot for immutable releases, replay, and rollback.
                    </div>
                  </>
                ) : (
                  <div className="mt-4 rounded-lg border border-border/75 bg-background/30 p-3.5">
                    <p className="text-[13px] font-medium text-foreground">
                      {isLoading ? 'Loading manager details…' : 'Manager details are temporarily unavailable.'}
                    </p>
                    <p className="mt-1 text-[11px] leading-5 text-muted">
                      The current snapshot selection remains visible. Manager metadata is supplied by the backend Registry and rendered when the catalog is available.
                    </p>
                  </div>
                )}
              </div>
            </ScrollArea>

            <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border/90 bg-background/20 px-4 py-3">
              <p className="min-w-0 truncate text-[10px] text-muted">
                {focused.catalogBacked
                  ? `${focused.strategyKey}${focused.isSystemDefault ? ' · system default' : ''}`
                  : 'Registry metadata unavailable'}
              </p>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                {incompatibleSkills && <p role="alert" className="max-w-xs text-xs text-amber-400">Disable installed Skills before selecting a manager without Skills support.</p>}
                <Button onClick={applySelection} disabled={!canApplySelection}>
                  {focusedIsCurrent ? 'Selected' : 'Select manager'}
                </Button>
              </div>
            </div>
          </section>
        </div>
      </Dialog>
    </>
  )
}
