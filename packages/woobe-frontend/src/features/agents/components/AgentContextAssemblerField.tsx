import { skillsConfig } from '@/features/skills/config'
import { useMemo, useState } from 'react'
import { BrainCircuit, Check, Settings2 } from 'lucide-react'
import { EmptyStatePanel, MetricTile, TechnicalListItem } from '@woobe/ui'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useContextManagers } from '@/features/agents/hooks'
import type { ContextManagerDescriptor } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { AgentContextConfigurationDialog } from './AgentContextConfigurationDialog'

const DEFAULT_CONTEXT_MANAGER = 'stdcm'

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function currentSelection(runtimeConfig: Record<string, unknown>) {
  const raw = recordValue(runtimeConfig.context_manager ?? runtimeConfig.context_assembler)
  return typeof raw.name === 'string' && raw.name.trim()
    ? raw.name.trim()
    : DEFAULT_CONTEXT_MANAGER
}

function DetailList({ items }: { items: string[] }) {
  if (!items.length) return <p className="font-sans text-product-caption text-muted-foreground">None declared.</p>
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

export function AgentContextAssemblerField({ projectId, compact = false }: { projectId: string; compact?: boolean }) {
  const { state, setField } = useAgentEditor()
  const { data: assemblers = [], isLoading, isError } = useContextManagers()
  const selectedName = useMemo(() => currentSelection(state.runtimeConfig), [state.runtimeConfig])

  const selectedFallback = useMemo<ContextManagerDescriptor>(() => ({
    name: selectedName,
    display_name: selectedName,
    description: '',
    behavior: '',
    recommended_for: [],
    capabilities: [],
    limitations: [],
    configuration: '',
    is_default: selectedName === DEFAULT_CONTEXT_MANAGER,
  }), [selectedName])

  const catalogOptions = useMemo(
    () => [...assemblers].sort((left, right) => {
      if (left.is_default !== right.is_default) return left.is_default ? -1 : 1
      return left.display_name.localeCompare(right.display_name)
    }),
    [assemblers],
  )

  const selectedDescriptor = catalogOptions.find(item => item.name === selectedName) ?? selectedFallback
  const availableOptions = catalogOptions.some(item => item.name === selectedName)
    ? catalogOptions
    : [selectedFallback, ...catalogOptions]

  const [open, setOpen] = useState(false)
  const [configureOpen, setConfigureOpen] = useState(false)
  const [focusedName, setFocusedName] = useState<string | null>(null)

  const focused = availableOptions.find(item => item.name === (focusedName || selectedName)) ?? selectedFallback
  const focusedIsCurrent = focused.name === selectedName
  const catalogReady = !isLoading && !isError && assemblers.length > 0
  const catalogBacked = assemblers.some(item => item.name === focused.name)
  const incompatibleSkills = skillsConfig(state.runtimeConfig).bindings.some(item => item.enabled) && !focused.supports_skills
  const canApplySelection = catalogReady && catalogBacked && !focusedIsCurrent && !incompatibleSkills

  const openSelector = () => {
    setFocusedName(selectedName)
    setOpen(true)
  }

  const applySelection = () => {
    if (!canApplySelection) return
    const nextRuntime = { ...state.runtimeConfig }
    delete nextRuntime.context_assembler
    nextRuntime.context_manager = { name: focused.name }
    setField('runtimeConfig', nextRuntime)
    setOpen(false)
  }

  return (
    <>
      <section aria-label="Context Manager" className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')}>
        <div className="mb-ui-sm">
          <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Context Manager</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Controls how context is managed before each Agent execution.</p>
        </div>

        <div className="rounded-container border border-border bg-background/35 p-ui-md">
          <div className="flex items-start gap-ui-sm">
            <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-primary/20 bg-primary/10 text-primary-light">
              <BrainCircuit className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="break-words font-mono text-system-label font-semibold text-slate-100">{selectedDescriptor.display_name}</p>
              <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{selectedName}</p>
              {selectedDescriptor.description ? <p className="mt-ui-sm line-clamp-2 font-sans text-product-caption text-muted-foreground">{selectedDescriptor.description}</p> : null}
            </div>
          </div>

          <div className="mt-ui-md grid grid-cols-2 gap-ui-sm border-t border-border/75 pt-ui-md">
            <Button type="button" size="sm" variant="outline" onClick={() => setConfigureOpen(true)} aria-label={`Configure context for ${selectedDescriptor.display_name}`}>
              <Settings2 className="h-3.5 w-3.5" />
              Configure
            </Button>
            <Button type="button" size="sm" variant="ghost" className="text-primary-light" onClick={openSelector} aria-label={`Change context manager. Current selection: ${selectedDescriptor.display_name}`}>
              Change
            </Button>
          </div>
        </div>
      </section>

      <AgentContextConfigurationDialog open={configureOpen} onClose={() => setConfigureOpen(false)} projectId={projectId} managerName={selectedDescriptor.display_name} />

      <Dialog open={open} onClose={() => setOpen(false)} title="Select a Context Manager" className="max-w-dialog-wide overflow-hidden bg-surface/95" contentClassName="p-0">
        <div className="grid h-dialog-workspace min-h-0 grid-cols-[15.625rem_minmax(0,1fr)] overflow-hidden">
          <aside className="flex min-h-0 flex-col border-r border-border/90 bg-background/25">
            <div className="shrink-0 border-b border-border/90 px-ui-lg py-ui-md">
              <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Registered managers</p>
              <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
                {isLoading ? 'Loading registry…' : isError ? 'Current selection only' : `${catalogOptions.length} available`}
              </p>
            </div>

            <ScrollArea className="min-h-0 flex-1 p-ui-md pr-ui-sm">
              <div className="space-y-ui-sm">
                {availableOptions.map((option) => {
                  const active = option.name === focused.name
                  const current = option.name === selectedName
                  return (
                    <TechnicalListItem
                      key={option.name}
                      selected={active}
                      disabled={!assemblers.some(item => item.name === option.name) && !current}
                      onClick={() => setFocusedName(option.name)}
                      leading={<BrainCircuit className="h-3.5 w-3.5 text-primary-light" />}
                      label={option.display_name}
                      description={option.name}
                      meta={option.is_default ? 'System default' : undefined}
                      trailing={current ? <span className="flex items-center gap-ui-xs font-mono text-system-meta uppercase text-primary-light"><Check className="h-3 w-3" />Selected</span> : null}
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
                    <BrainCircuit className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-ui-sm">
                      <h3 className="font-mono text-system-heading font-semibold text-slate-50">{focused.display_name}</h3>
                      <span className="rounded-technical border border-border px-ui-xs py-ui-hairline font-mono text-system-meta text-muted-foreground">{focused.name}</span>
                      {focusedIsCurrent ? <span className="rounded-technical border border-primary/30 bg-primary/10 px-ui-xs py-ui-hairline font-mono text-system-meta uppercase text-primary-light">Selected</span> : null}
                      {focused.is_default ? <span className="rounded-technical border border-border bg-background/40 px-ui-xs py-ui-hairline font-mono text-system-meta uppercase text-muted-foreground">System default</span> : null}
                    </div>
                    <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
                      {focused.is_default ? 'System default manager' : 'Registered manager'}
                    </p>
                  </div>
                </div>

                {catalogReady && catalogBacked ? (
                  <>
                    <div className="mt-ui-lg grid gap-ui-sm sm:grid-cols-2">
                      <MetricTile label="Manager" value={focused.name} />
                      <MetricTile label="Configuration" value={focused.configuration || 'Default'} />
                    </div>

                    <div className="mt-ui-lg grid gap-ui-lg border-t border-border/75 pt-ui-lg md:grid-cols-2">
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Description</p><p className="mt-ui-sm font-sans text-product-body text-slate-200">{focused.description}</p></div>
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">How it operates</p><p className="mt-ui-sm font-sans text-product-body text-slate-300">{focused.behavior}</p></div>
                    </div>

                    <div className="mt-ui-lg border-t border-border/75 pt-ui-lg">
                      <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Recommended for</p>
                      <div className="mt-ui-sm grid gap-x-ui-xl gap-y-ui-xs sm:grid-cols-2"><DetailList items={focused.recommended_for} /></div>
                    </div>

                    <div className="mt-ui-lg grid gap-ui-xl border-t border-border/75 pt-ui-lg md:grid-cols-2">
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Capabilities</p><div className="mt-ui-sm"><DetailList items={focused.capabilities} /></div></div>
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Limitations</p><div className="mt-ui-sm"><DetailList items={focused.limitations} /></div></div>
                    </div>

                    <div className="mt-ui-lg rounded-container border border-border/75 bg-background/30 px-ui-md py-ui-md font-sans text-product-small text-muted-foreground">
                      The Agent snapshot stores the selected Context Manager name: <span className="font-mono text-slate-200">{focused.name}</span>.
                    </div>
                  </>
                ) : (
                  <div className="mt-ui-lg"><EmptyStatePanel compact title={isLoading ? 'Loading manager details…' : 'Manager details unavailable'} description="The current manager name remains visible. Registry metadata appears when the backend catalog is available." /></div>
                )}
              </div>
            </ScrollArea>

            <div className="flex shrink-0 items-center justify-between gap-ui-md border-t border-border/90 bg-background/20 px-ui-lg py-ui-md">
              <p className="min-w-0 truncate font-sans text-product-caption text-muted-foreground">{catalogBacked ? `${focused.name}${focused.is_default ? ' · system default' : ''}` : 'Registry metadata unavailable'}</p>
              <div className="flex shrink-0 items-center gap-ui-sm">
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                {incompatibleSkills && <p role="alert" className="max-w-xs font-sans text-product-caption text-amber-400">Disable installed Skills before selecting a manager without Skills support.</p>}
                <Button onClick={applySelection} disabled={!canApplySelection}>{focusedIsCurrent ? 'Selected' : 'Select manager'}</Button>
              </div>
            </div>
          </section>
        </div>
      </Dialog>
    </>
  )
}
