import { skillsConfig } from '@/features/skills/config'
import { useMemo, useState } from 'react'
import { BrainCircuit, Check, Settings2 } from 'lucide-react'
import { EmptyStatePanel, MetricTile, TechnicalListItem } from '@woobe/ui'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useContextAssemblers } from '@/features/agents/hooks'
import type { ContextAssemblerDescriptor } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { AgentContextConfigurationDialog } from './AgentContextConfigurationDialog'

const DEFAULT_CONTEXT_MANAGER = 'standard'

type ContextManagerOption = {
  name: string
  descriptor: ContextAssemblerDescriptor
  catalogBacked: boolean
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function normalizeManagerName(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) return DEFAULT_CONTEXT_MANAGER
  const normalized = value.trim().toLowerCase()
  if (['stdcm', 'default', 'stdcm:v1', 'stdcm:v2', 'default:v1'].includes(normalized)) return DEFAULT_CONTEXT_MANAGER
  return normalized
}

function currentSelection(runtimeConfig: Record<string, unknown>): string {
  const selection = runtimeConfig.context_assembler
  if (typeof selection === 'string') return normalizeManagerName(selection)
  const raw = recordValue(selection)
  const legacyStrategyName = raw.strategy_name
  return normalizeManagerName(
    typeof legacyStrategyName === 'string' && legacyStrategyName.trim()
      ? legacyStrategyName
      : raw.name,
  )
}

function DetailList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="font-sans text-product-caption text-muted-foreground">None declared.</p>
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

export function AgentContextAssemblerField({ projectId, compact = false }: { projectId: string; compact?: boolean }) {
  const { state, setField } = useAgentEditor()
  const { data: assemblers = [], isLoading, isError } = useContextAssemblers()
  const selectedName = useMemo(() => currentSelection(state.runtimeConfig), [state.runtimeConfig])

  const selectedFallback = useMemo<ContextAssemblerDescriptor>(() => ({
    name: selectedName,
    display_name: selectedName,
    description: '',
    behavior: '',
    recommended_for: [],
    capabilities: [],
    limitations: [],
    configuration: '',
    supports_skills: false,
    is_default: selectedName === DEFAULT_CONTEXT_MANAGER,
  }), [selectedName])

  const catalogOptions = useMemo<ContextManagerOption[]>(() => (
    assemblers
      .map((descriptor) => ({
        name: descriptor.name,
        descriptor,
        catalogBacked: true,
      }))
      .sort((left, right) => {
        if (left.descriptor.is_default !== right.descriptor.is_default) {
          return left.descriptor.is_default ? -1 : 1
        }
        return left.descriptor.display_name.localeCompare(right.descriptor.display_name)
      })
  ), [assemblers])

  const selectedCatalogOption = catalogOptions.find((option) => option.name === selectedName)
  const selectedDescriptor = selectedCatalogOption?.descriptor ?? selectedFallback
  const selectedFallbackOption = useMemo<ContextManagerOption>(() => ({
    name: selectedName,
    descriptor: selectedFallback,
    catalogBacked: false,
  }), [selectedName, selectedFallback])
  const availableOptions = selectedCatalogOption ? catalogOptions : [selectedFallbackOption, ...catalogOptions]

  const [open, setOpen] = useState(false)
  const [configureOpen, setConfigureOpen] = useState(false)
  const [focusedName, setFocusedName] = useState<string | null>(null)

  const focused = availableOptions.find((option) => option.name === (focusedName || selectedName)) ?? selectedFallbackOption
  const focusedDescriptor = focused.descriptor
  const focusedIsCurrent = focused.name === selectedName
  const catalogReady = !isLoading && !isError && assemblers.length > 0
  const incompatibleSkills = skillsConfig(state.runtimeConfig).bindings.some(item => item.enabled) && !focusedDescriptor.supports_skills
  const canApplySelection = catalogReady && focused.catalogBacked && !focusedIsCurrent && !incompatibleSkills

  const openSelector = () => {
    setFocusedName(selectedName)
    setOpen(true)
  }

  const applySelection = () => {
    if (!canApplySelection) return
    setField('runtimeConfig', {
      ...state.runtimeConfig,
      context_assembler: { name: focused.name },
    })
    setOpen(false)
  }

  return (
    <>
      <section aria-label="Context Manager" className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')}>
        <div className="mb-ui-sm">
          <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Context Manager</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Controls how context is assembled before each Agent execution.</p>
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
            <Button type="button" size="sm" variant="outline" onClick={() => setConfigureOpen(true)} aria-label={'Configure context for ' + selectedDescriptor.display_name}>
              <Settings2 className="h-3.5 w-3.5" />
              Configure
            </Button>
            <Button type="button" size="sm" variant="ghost" className="text-primary-light" onClick={openSelector} aria-label={'Change context manager. Current selection: ' + selectedDescriptor.display_name}>
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
                {isLoading ? 'Loading registry…' : isError ? 'Current selection only' : String(catalogOptions.length) + ' available'}
              </p>
            </div>

            <ScrollArea className="min-h-0 flex-1 p-ui-md pr-ui-sm">
              <div className="space-y-ui-sm">
                {availableOptions.map((option) => {
                  const active = option.name === focused.name
                  const current = option.name === selectedName
                  const item = option.descriptor
                  return (
                    <TechnicalListItem
                      key={option.name}
                      selected={active}
                      disabled={!option.catalogBacked && !current}
                      onClick={() => setFocusedName(option.name)}
                      leading={<BrainCircuit className="h-3.5 w-3.5 text-primary-light" />}
                      label={item.display_name}
                      description={option.name}
                      meta={item.is_default ? 'System default' : undefined}
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
                      <h3 className="font-mono text-system-heading font-semibold text-slate-50">{focusedDescriptor.display_name}</h3>
                      <span className="rounded-technical border border-border px-ui-xs py-ui-hairline font-mono text-system-meta text-muted-foreground">{focused.name}</span>
                      {focusedIsCurrent ? <span className="rounded-technical border border-primary/30 bg-primary/10 px-ui-xs py-ui-hairline font-mono text-system-meta uppercase text-primary-light">Selected</span> : null}
                      {focusedDescriptor.is_default ? <span className="rounded-technical border border-border bg-background/40 px-ui-xs py-ui-hairline font-mono text-system-meta uppercase text-muted-foreground">System default</span> : null}
                    </div>
                    <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
                      {focusedDescriptor.is_default ? 'System default manager' : 'Registered manager'}
                    </p>
                  </div>
                </div>

                {catalogReady && focused.catalogBacked ? (
                  <>
                    <div className="mt-ui-lg grid gap-ui-sm sm:grid-cols-3">
                      <MetricTile label="Selection" value={focused.name} />
                      <MetricTile label="Identity" value={focusedDescriptor.name} />
                      <MetricTile label="Configuration" value={focusedDescriptor.configuration || 'Default'} />
                    </div>

                    <div className="mt-ui-lg grid gap-ui-lg border-t border-border/75 pt-ui-lg md:grid-cols-2">
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Description</p><p className="mt-ui-sm font-sans text-product-body text-slate-200">{focusedDescriptor.description}</p></div>
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">How it operates</p><p className="mt-ui-sm font-sans text-product-body text-slate-300">{focusedDescriptor.behavior}</p></div>
                    </div>

                    <div className="mt-ui-lg border-t border-border/75 pt-ui-lg">
                      <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Recommended for</p>
                      <div className="mt-ui-sm grid gap-x-ui-xl gap-y-ui-xs sm:grid-cols-2"><DetailList items={focusedDescriptor.recommended_for} /></div>
                    </div>

                    <div className="mt-ui-lg grid gap-ui-xl border-t border-border/75 pt-ui-lg md:grid-cols-2">
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Capabilities</p><div className="mt-ui-sm"><DetailList items={focusedDescriptor.capabilities} /></div></div>
                      <div><p className="font-mono text-system-meta font-semibold uppercase tracking-[0.12em] text-muted-foreground">Limitations</p><div className="mt-ui-sm"><DetailList items={focusedDescriptor.limitations} /></div></div>
                    </div>

                    <div className="mt-ui-lg rounded-container border border-border/75 bg-background/30 px-ui-md py-ui-md font-sans text-product-small text-muted-foreground">
                      Selecting <span className="font-mono text-slate-200">{focused.name}</span> freezes the stable Context Manager identity in the Agent snapshot.
                    </div>
                  </>
                ) : (
                  <div className="mt-ui-lg"><EmptyStatePanel compact title={isLoading ? 'Loading manager details…' : 'Manager details unavailable'} description="The current snapshot selection remains visible. Registry metadata appears when the backend catalog is available." /></div>
                )}
              </div>
            </ScrollArea>

            <div className="flex shrink-0 items-center justify-between gap-ui-md border-t border-border/90 bg-background/20 px-ui-lg py-ui-md">
              <p className="min-w-0 truncate font-sans text-product-caption text-muted-foreground">{focused.catalogBacked ? focused.name + (focusedDescriptor.is_default ? ' · system default' : '') : 'Registry metadata unavailable'}</p>
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
