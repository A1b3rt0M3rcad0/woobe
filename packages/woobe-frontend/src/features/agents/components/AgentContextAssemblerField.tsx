import { useMemo, useState } from 'react'
import { BrainCircuit, Check, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useContextAssemblers } from '@/features/agents/hooks'
import type { ContextAssemblerDescriptor } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

const DEFAULT_SELECTION = { name: 'default', version: 'v1' }

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function currentSelection(runtimeConfig: Record<string, unknown>) {
  const raw = recordValue(runtimeConfig.context_assembler)
  return {
    name: typeof raw.name === 'string' && raw.name.trim() ? raw.name : DEFAULT_SELECTION.name,
    version: typeof raw.version === 'string' && raw.version.trim() ? raw.version : DEFAULT_SELECTION.version,
  }
}

function descriptorKey(item: Pick<ContextAssemblerDescriptor, 'name' | 'version'>) {
  return `${item.name}:${item.version}`
}

export function AgentContextAssemblerField() {
  const { state, setField } = useAgentEditor()
  const { data: assemblers = [], isLoading, isError } = useContextAssemblers()
  const selected = useMemo(() => currentSelection(state.runtimeConfig), [state.runtimeConfig])
  const selectedKey = descriptorKey(selected)
  const selectedDescriptor = assemblers.find((item) => descriptorKey(item) === selectedKey)
  const [open, setOpen] = useState(false)
  const [focusedKey, setFocusedKey] = useState<string | null>(null)

  const focused = assemblers.find((item) => descriptorKey(item) === (focusedKey || selectedKey))
    ?? selectedDescriptor
    ?? assemblers[0]

  const openSelector = () => {
    setFocusedKey(selectedKey)
    setOpen(true)
  }

  const applySelection = () => {
    if (!focused) return
    setField('runtimeConfig', {
      ...state.runtimeConfig,
      context_assembler: {
        name: focused.name,
        version: focused.version,
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
          <span className="truncate text-sm font-medium text-foreground">{selected.name}</span>
          <span className="shrink-0 rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">
            {selectedKey}
          </span>
          <ChevronRight className="ml-auto h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
        </button>
      </section>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Select a Context Manager"
        className="max-w-4xl overflow-hidden bg-surface/95"
      >
        <div className="grid max-h-[70vh] min-h-[440px] grid-cols-[260px_minmax(0,1fr)] overflow-hidden -m-6">
          <aside className="flex min-h-0 flex-col border-r border-border/90 bg-background/25">
            <div className="border-b border-border/90 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Registered managers</p>
              <p className="mt-1 text-[11px] text-muted">
                {isLoading ? 'Loading registry…' : `${assemblers.length} available`}
              </p>
            </div>

            <div className="min-h-0 flex-1 p-3">
              {isLoading ? (
                <div className="rounded-lg border border-border/80 bg-background/40 p-3 text-xs text-muted">
                  Loading context managers…
                </div>
              ) : isError ? (
                <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-xs text-danger">
                  Could not load the registry.
                </div>
              ) : assemblers.length === 0 ? (
                <div className="rounded-lg border border-border/80 bg-background/40 p-3 text-xs text-muted">
                  No context managers registered.
                </div>
              ) : (
                <ScrollArea className="h-full pr-1">
                  <div className="space-y-2">
                    {assemblers.map((item) => {
                      const key = descriptorKey(item)
                      const active = key === descriptorKey(focused || selected)
                      const current = key === selectedKey
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => setFocusedKey(key)}
                          className={cn(
                            'flex w-full items-center gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors',
                            active
                              ? 'border-primary/60 bg-primary/10'
                              : 'border-border/80 bg-background/35 hover:border-primary/30 hover:bg-accent/30',
                          )}
                        >
                          <BrainCircuit className={cn('h-4 w-4 shrink-0', active ? 'text-primary' : 'text-muted')} />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-foreground">{item.name}</span>
                            <span className="mt-0.5 block truncate font-mono text-[9px] text-muted">{key}</span>
                          </span>
                          {current ? <Check className="h-4 w-4 shrink-0 text-primary" /> : null}
                        </button>
                      )
                    })}
                  </div>
                </ScrollArea>
              )}
            </div>
          </aside>

          <section className="flex min-h-0 flex-col">
            <div className="min-h-0 flex-1 p-6">
              {focused ? (
                <div className="max-w-2xl">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
                    <BrainCircuit className="h-4 w-4" />
                  </div>

                  <div className="mt-5 flex flex-wrap items-center gap-2">
                    <h3 className="text-xl font-semibold text-foreground">{focused.display_name}</h3>
                    <span className="rounded border border-border px-2 py-0.5 font-mono text-[10px] text-muted">
                      {descriptorKey(focused)}
                    </span>
                    {focused.is_default ? (
                      <span className="rounded border border-border px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-muted">
                        Default
                      </span>
                    ) : null}
                  </div>

                  <p className="mt-3 text-sm leading-relaxed text-muted">{focused.description}</p>

                  <div className="mt-6 border-t border-border/80 pt-5">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">How it operates</p>
                    <p className="mt-2 text-sm leading-6 text-foreground/80">{focused.behavior}</p>
                  </div>

                  <div className="mt-6 space-y-3 border-t border-border/80 pt-5 text-xs leading-5 text-muted">
                    <div className="flex gap-2.5">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <span>Used to assemble context for Model Invocations.</span>
                    </div>
                    <div className="flex gap-2.5">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <span>The exact <span className="font-mono text-foreground">name:version</span> is stored in the Agent snapshot.</span>
                    </div>
                    <div className="flex gap-2.5">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <span>Immutable releases preserve the selection for replay and rollback.</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted">
                  Select a registered manager to inspect its behavior.
                </div>
              )}
            </div>

            <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={applySelection} disabled={!focused || isLoading || isError}>Select manager</Button>
            </div>
          </section>
        </div>
      </Dialog>
    </>
  )
}
