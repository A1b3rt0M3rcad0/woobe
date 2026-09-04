import { useMemo, useState } from 'react'
import { BrainCircuit, Check, ChevronRight } from 'lucide-react'

import { Dialog } from '@/components/ui/Dialog'
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
      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <div>
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">Context Management</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              Selects how context is assembled for every Model Invocation. The exact manager and version are part of the Agent snapshot.
            </p>
          </div>

          <button
            type="button"
            onClick={openSelector}
            className="group flex w-full items-center gap-3 rounded-lg border border-border bg-background/40 p-3 text-left transition-colors hover:border-primary/40 hover:bg-accent/40"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
              <BrainCircuit className="h-4 w-4 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">
                  {selectedDescriptor?.display_name || selected.name}
                </span>
                <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">
                  {selectedKey}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">
                {selectedDescriptor?.description || 'Registered Context Manager selected by this Agent snapshot.'}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
          </button>

          <p className="text-[11px] leading-relaxed text-muted">
            Draft changes flow to Staging and Production through immutable releases, preserving this selection for replay and rollback.
          </p>
        </div>
      </div>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Context Manager"
        className="max-w-3xl"
        scrollMode="content"
      >
        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium text-foreground">Registered managers</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              This list comes from the Context Assembler Registry supported by the running Woobe instance.
            </p>
          </div>

          {isLoading ? (
            <div className="rounded-lg border border-border p-4 text-sm text-muted">Loading registered context managers...</div>
          ) : isError ? (
            <div className="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
              Could not load the Context Assembler Registry.
            </div>
          ) : assemblers.length === 0 ? (
            <div className="rounded-lg border border-border p-4 text-sm text-muted">No context managers are registered.</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
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
                        'w-full rounded-lg border p-3 text-left transition-colors',
                        active
                          ? 'border-primary/60 bg-primary/10'
                          : 'border-border bg-background/30 hover:border-primary/30 hover:bg-accent/30',
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium text-foreground">{item.display_name}</span>
                            {item.is_default && (
                              <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">Default</span>
                            )}
                          </div>
                          <span className="mt-1 block font-mono text-[10px] text-muted">{key}</span>
                        </div>
                        {current && <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
                      </div>
                    </button>
                  )
                })}
              </div>

              <div className="rounded-lg border border-border bg-background/30 p-4">
                {focused ? (
                  <div className="space-y-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-foreground">{focused.display_name}</h3>
                        <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">
                          {descriptorKey(focused)}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-relaxed text-muted">{focused.description}</p>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">How it operates</p>
                      <p className="mt-2 text-xs leading-relaxed text-foreground/80">{focused.behavior}</p>
                    </div>
                    <div className="rounded-lg border border-border bg-surface/60 p-3 text-[11px] leading-relaxed text-muted">
                      The selected <span className="font-mono text-foreground">name:version</span> is frozen into the Agent runtime snapshot. Existing releases do not silently switch when new manager versions are registered.
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted transition-colors hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={applySelection}
              disabled={!focused || isLoading || isError}
              className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
            >
              Use this manager
            </button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
