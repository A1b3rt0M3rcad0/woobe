import { useEffect, useRef, useState } from 'react'
import { ChevronDown, X } from 'lucide-react'
import { toast } from 'sonner'

import { useAgentRuntimeEnvironments, useUpdateAgentRuntimeEnvironment } from '@/features/agents/hooks'
import type { Agent, RuntimeEnvironment } from '@/features/agents/types'
import { cn } from '@/lib/utils'

const environments: RuntimeEnvironment[] = ['draft', 'staging', 'production']

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function AgentControlsPopover({
  agent,
  projectId,
}: {
  agent: Agent
  projectId: string
}) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const [open, setOpen] = useState(false)
  const statesQuery = useAgentRuntimeEnvironments(agent.id, projectId)
  const updateRuntime = useUpdateAgentRuntimeEnvironment(agent.id, projectId)

  const enabledCount = environments.filter(
    (environment) => statesQuery.data?.[environment]?.enabled ?? true,
  ).length

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: PointerEvent) {
      const target = event.target
      if (target instanceof Node && rootRef.current && !rootRef.current.contains(target)) setOpen(false)
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  async function updateEnabled(environment: RuntimeEnvironment, enabled: boolean) {
    if (updateRuntime.isPending) return

    try {
      await updateRuntime.mutateAsync({ environment, enabled })
      toast.success(`${titleCase(environment)} Agent runtime ${enabled ? 'enabled' : 'disabled'}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Agent runtime')
    }
  }

  return (
    <div ref={rootRef} className="relative z-[210] flex items-center">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'inline-flex h-8 items-center gap-2 rounded-lg border px-2.5 text-xs font-medium transition-colors',
          open
            ? 'border-primary/30 bg-primary/10 text-white shadow-sm shadow-primary/5'
            : 'border-border/80 bg-background/55 text-muted hover:border-primary/30 hover:bg-primary/5 hover:text-white',
        )}
        title="Agent runtime environments"
      >
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            enabledCount === environments.length
              ? 'bg-emerald-400'
              : enabledCount === 0
                ? 'bg-slate-500'
                : 'bg-amber-400',
          )}
        />
        <span className="text-slate-200">Runtime</span>
        <span className="text-muted">{enabledCount}/{environments.length}</span>
        <ChevronDown className={cn('h-3.5 w-3.5 text-muted transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-[1000] w-[310px] overflow-hidden rounded-xl border border-border/90 bg-surface/95 shadow-xl shadow-black/30 backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-border/80 px-3 py-2.5">
            <div>
              <p className="text-xs font-semibold text-white">Agent runtime</p>
              <p className="mt-0.5 text-[11px] text-muted">Control direct Agent Runs by environment.</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md p-1 text-muted hover:bg-background/60 hover:text-white"
              aria-label="Close runtime controls"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="divide-y divide-border/70">
            {environments.map((environment) => {
              const enabled = statesQuery.data?.[environment]?.enabled ?? true

              return (
                <div key={environment} className="flex items-center justify-between gap-3 px-3 py-2.5">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', enabled ? 'bg-emerald-400' : 'bg-slate-500')} />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-white">{titleCase(environment)}</p>
                      <p className="text-[10px] text-muted">{enabled ? 'Runs allowed' : 'Runs blocked'}</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    aria-pressed={enabled}
                    disabled={updateRuntime.isPending || statesQuery.isLoading}
                    onClick={() => void updateEnabled(environment, !enabled)}
                    className={cn(
                      'relative h-5 w-9 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                      enabled ? 'border-emerald-400/40 bg-emerald-500/25' : 'border-border/80 bg-surface/70',
                    )}
                    title={enabled ? `Disable ${environment} runtime` : `Enable ${environment} runtime`}
                  >
                    <span
                      className={cn(
                        'absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
                        enabled ? 'translate-x-4' : 'translate-x-0',
                      )}
                    />
                  </button>
                </div>
              )
            })}
          </div>

          <p className="border-t border-border/80 px-3 py-2 text-[10px] leading-4 text-muted/80">
            Existing Runs continue. Network executions use the Network runtime.
          </p>
        </div>
      )}
    </div>
  )
}
