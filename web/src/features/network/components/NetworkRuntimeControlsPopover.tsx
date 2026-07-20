import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Power, PowerOff, Workflow, X } from 'lucide-react'
import { toast } from 'sonner'

import type { RuntimeEnvironment } from '@/features/agents/types'
import { useNetworkRuntimeEnvironments, useUpdateNetworkRuntimeEnvironment } from '@/features/network/hooks'
import { cn } from '@/lib/utils'

const environments: RuntimeEnvironment[] = ['draft', 'staging', 'production']

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function NetworkRuntimeControlsPopover({
  networkId,
  projectId,
  environment,
}: {
  networkId: string
  projectId: string
  environment?: RuntimeEnvironment
}) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const [open, setOpen] = useState(false)
  const statesQuery = useNetworkRuntimeEnvironments(networkId, projectId)
  const updateRuntime = useUpdateNetworkRuntimeEnvironment(networkId, projectId)
  const visibleEnvironments = environment ? [environment] : environments
  const selectedEnabled = environment ? statesQuery.data?.[environment]?.enabled ?? true : null

  useEffect(() => {
    if (!open) return
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target
      if (target instanceof Node && rootRef.current && !rootRef.current.contains(target)) setOpen(false)
    }
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  async function updateEnabled(targetEnvironment: RuntimeEnvironment, enabled: boolean) {
    if (updateRuntime.isPending) return
    try {
      await updateRuntime.mutateAsync({ environment: targetEnvironment, enabled })
      toast.success(`${titleCase(targetEnvironment)} Network runtime ${enabled ? 'enabled' : 'disabled'}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Network runtime')
    }
  }

  return (
    <div ref={rootRef} className="relative z-[210] flex items-center">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'inline-flex h-8 items-center gap-2 rounded-lg border px-2.5 text-[10px] font-medium transition-colors',
          open
            ? 'border-primary/30 bg-primary/10 text-white'
            : 'border-border/80 bg-background/45 text-muted hover:border-primary/30 hover:text-white',
        )}
        title={environment ? `${titleCase(environment)} Network runtime` : 'Network runtime environments'}
      >
        <Workflow className="h-3.5 w-3.5" />
        <span>Network</span>
        {environment ? (
          <>
            <span className={cn('h-1.5 w-1.5 rounded-full', selectedEnabled ? 'bg-emerald-400' : 'bg-slate-500')} />
            <span>{selectedEnabled ? 'On' : 'Off'}</span>
          </>
        ) : (
          <span className="text-muted">Runtime</span>
        )}
        <ChevronDown className={cn('h-3 w-3 transition-transform', open && 'rotate-180')} />
      </button>

      {open ? (
        <div className="absolute right-0 top-10 z-[1000] w-[380px] overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/35 backdrop-blur-md">
          <div className="flex items-start justify-between gap-3 border-b border-border/80 bg-background/20 px-4 py-3.5">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{environment ? `${titleCase(environment)} Network runtime` : 'Network runtime environments'}</p>
              <p className="mt-1 text-xs leading-5 text-muted">Controls admission of new executions for the complete Network.</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1 text-muted hover:bg-background/60 hover:text-white"><X className="h-4 w-4" /></button>
          </div>
          <div className="space-y-2 p-3.5">
            {visibleEnvironments.map((targetEnvironment) => {
              const enabled = statesQuery.data?.[targetEnvironment]?.enabled ?? true
              return (
                <section key={targetEnvironment} className="rounded-xl border border-border/80 bg-background/45 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className={cn('flex h-7 w-7 items-center justify-center rounded-lg border', enabled ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300' : 'border-border/70 bg-surface/50 text-muted')}>
                        {enabled ? <Power className="h-3.5 w-3.5" /> : <PowerOff className="h-3.5 w-3.5" />}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-white">{titleCase(targetEnvironment)}</p>
                        <p className="mt-0.5 text-xs leading-5 text-muted">{enabled ? 'New Network Runs are allowed.' : 'New Network Runs are blocked.'}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      aria-pressed={enabled}
                      disabled={updateRuntime.isPending || statesQuery.isLoading}
                      onClick={() => void updateEnabled(targetEnvironment, !enabled)}
                      className={cn('relative h-5 w-9 shrink-0 rounded-full border transition-colors disabled:opacity-60', enabled ? 'border-emerald-400/40 bg-emerald-500/25' : 'border-border/80 bg-surface/70')}
                    >
                      <span className={cn('absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform', enabled ? 'translate-x-4' : 'translate-x-0')} />
                    </button>
                  </div>
                </section>
              )
            })}
            <p className="px-1 pt-1 text-[11px] leading-4 text-muted/80">Existing Runs continue. Canvas, traces, version management, promotion and rollback remain available. Agent standalone switches do not affect this Network.</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}
