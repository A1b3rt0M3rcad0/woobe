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
          'inline-flex h-control-sm items-center gap-ui-xs rounded-control border px-ui-sm font-mono text-system-micro transition-colors',
          open
            ? 'border-primary/35 bg-primary/[0.10] text-slate-50'
            : 'border-border bg-control/40 text-muted-foreground hover:bg-control hover:text-slate-50',
        )}
        title="Agent runtime environments"
      >
        <span className={cn('h-1.5 w-1.5 rounded-full', enabledCount === environments.length ? 'bg-emerald-400' : enabledCount === 0 ? 'bg-slate-500' : 'bg-amber-400')} />
        <span>Runtime</span>
        <span className="text-muted-foreground">{enabledCount}/{environments.length}</span>
        <ChevronDown className={cn('h-3 w-3 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-[1000] w-[300px] overflow-hidden rounded-container border border-border bg-surface/[0.98]">
          <div className="flex min-h-panel-header items-center justify-between border-b border-border px-ui-md py-ui-sm">
            <div>
              <p className="font-mono text-system-label font-bold text-slate-50">Agent runtime</p>
              <p className="mt-ui-hairline font-sans text-product-caption text-muted-foreground">Control direct Agent Runs by environment.</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50" aria-label="Close runtime controls">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="divide-y divide-border/70">
            {environments.map((environment) => {
              const enabled = statesQuery.data?.[environment]?.enabled ?? true
              return (
                <div key={environment} className="flex min-h-panel-header items-center justify-between gap-ui-md px-ui-md py-ui-sm">
                  <div className="flex min-w-0 items-center gap-ui-sm">
                    <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', enabled ? 'bg-emerald-400' : 'bg-slate-500')} />
                    <div className="min-w-0">
                      <p className="font-mono text-system-label font-semibold text-slate-100">{titleCase(environment)}</p>
                      <p className="mt-ui-hairline font-sans text-product-caption text-muted-foreground">{enabled ? 'Runs allowed' : 'Runs blocked'}</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    aria-pressed={enabled}
                    disabled={updateRuntime.isPending || statesQuery.isLoading}
                    onClick={() => void updateEnabled(environment, !enabled)}
                    className={cn('relative h-4 w-8 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60', enabled ? 'border-emerald-400/35 bg-emerald-500/[0.16]' : 'border-border bg-control')}
                    title={enabled ? `Disable ${environment} runtime` : `Enable ${environment} runtime`}
                  >
                    <span className={cn('absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-slate-100 transition-transform', enabled ? 'translate-x-4' : 'translate-x-0')} />
                  </button>
                </div>
              )
            })}
          </div>

          <p className="border-t border-border px-ui-md py-ui-sm font-sans text-system-micro leading-4 text-muted-foreground">
            Existing Runs continue. Network executions use the Network runtime.
          </p>
        </div>
      )}
    </div>
  )
}
