import { useEffect, useRef, useState } from 'react'
import { Activity, Check, ChevronDown, Database, Power, PowerOff, X } from 'lucide-react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { Agent } from '@/features/agents/types'

type RuntimeStatus = 'active' | 'inactive'
type RuntimeSessionMode = 'stateful' | 'stateless'

function normalizeStatus(value?: string): RuntimeStatus {
  return value === 'inactive' ? 'inactive' : 'active'
}

function normalizeSessionMode(value?: string): RuntimeSessionMode {
  return value === 'stateless' ? 'stateless' : 'stateful'
}

export function AgentControlsPopover({ agent }: { agent: Agent }) {
  const updateAgent = useUpdateAgent(agent.id)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<RuntimeStatus>(normalizeStatus(agent.status))
  const [sessionMode, setSessionMode] = useState<RuntimeSessionMode>(normalizeSessionMode(agent.session_mode))
  const isAgentOn = status === 'active'

  useEffect(() => {
    setStatus(normalizeStatus(agent.status))
    setSessionMode(normalizeSessionMode(agent.session_mode))
  }, [agent.status, agent.session_mode])

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: PointerEvent) {
      const target = event.target
      if (target instanceof Node && rootRef.current && !rootRef.current.contains(target)) {
        setOpen(false)
      }
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

  async function updateStatus(nextStatus: RuntimeStatus) {
    if (nextStatus === status || updateAgent.isPending) return
    setStatus(nextStatus)
    try {
      await updateAgent.mutateAsync({ status: nextStatus })
      toast.success(nextStatus === 'active' ? 'Agent enabled' : 'Agent disabled')
    } catch (error) {
      setStatus(normalizeStatus(agent.status))
      toast.error(error instanceof Error ? error.message : 'Failed to update agent status')
    }
  }

  async function updateSessionMode(nextMode: RuntimeSessionMode) {
    if (nextMode === sessionMode || updateAgent.isPending) return
    setSessionMode(nextMode)
    try {
      await updateAgent.mutateAsync({ session_mode: nextMode })
      toast.success(nextMode === 'stateful' ? 'Session memory enabled' : 'Session memory disabled')
    } catch (error) {
      setSessionMode(normalizeSessionMode(agent.session_mode))
      toast.error(error instanceof Error ? error.message : 'Failed to update session mode')
    }
  }

  return (
    <div ref={rootRef} className="relative flex items-center">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'inline-flex h-8 items-center gap-2 rounded-lg border px-2.5 text-xs font-medium transition-colors',
          open
            ? 'border-primary/30 bg-primary/10 text-white shadow-sm shadow-primary/5'
            : 'border-border/80 bg-background/55 text-muted hover:border-primary/30 hover:bg-primary/5 hover:text-white',
        )}
        title="Agent controls"
      >
        <span className={cn('h-1.5 w-1.5 rounded-full', isAgentOn ? 'bg-emerald-400' : 'bg-slate-500')} />
        <span className="text-slate-200">Agent</span>
        <span className={cn('font-medium', isAgentOn ? 'text-emerald-300' : 'text-slate-400')}>{isAgentOn ? 'Active' : 'Inactive'}</span>
        <span className="hidden text-muted/60 xl:inline">·</span>
        <span className="hidden text-muted xl:inline">{sessionMode === 'stateful' ? 'Stateful' : 'Stateless'}</span>
        <ChevronDown className={cn('h-3.5 w-3.5 text-muted transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-[360px] overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/35 backdrop-blur-md">
          <div className="flex items-start justify-between gap-3 border-b border-border/80 bg-background/20 px-4 py-3.5">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">Agent Controls</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Global settings. Applies to Playground, API, Staging and Production.
              </p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-transparent p-1 text-muted hover:border-border/80 hover:bg-background/60 hover:text-white">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-2.5 p-3.5">
            <section className="rounded-xl border border-border/80 bg-background/45 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2.5">
                  <span className={cn('flex h-7 w-7 items-center justify-center rounded-lg border', isAgentOn ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300' : 'border-border/70 bg-surface/50 text-muted')}>
                    {isAgentOn ? <Power className="h-3.5 w-3.5" /> : <PowerOff className="h-3.5 w-3.5" />}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-white">Execution</p>
                      <span className={cn('rounded-md border px-1.5 py-0.5 text-[10px] font-medium', isAgentOn ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300' : 'border-border/70 bg-surface/50 text-muted')}>
                        {isAgentOn ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs leading-5 text-muted">
                      {isAgentOn ? 'Runtime calls are allowed.' : 'Runtime calls are blocked.'}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  aria-pressed={isAgentOn}
                  disabled={updateAgent.isPending}
                  onClick={() => void updateStatus(isAgentOn ? 'inactive' : 'active')}
                  className={cn(
                    'relative h-6 w-10 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                    isAgentOn ? 'border-emerald-400/40 bg-emerald-500/25' : 'border-border/80 bg-surface/70',
                  )}
                  title={isAgentOn ? 'Disable agent execution' : 'Enable agent execution'}
                >
                  <span className={cn('absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform', isAgentOn ? 'translate-x-4' : 'translate-x-0.5')} />
                </button>
              </div>
            </section>

            <section className="rounded-xl border border-border/80 bg-background/45 p-3">
              <div className="mb-3 flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-border/70 bg-surface/50 text-muted">
                  {sessionMode === 'stateful' ? <Database className="h-3.5 w-3.5" /> : <Activity className="h-3.5 w-3.5" />}
                </span>
                <div>
                  <p className="text-sm font-medium text-white">Session mode</p>
                  <p className="mt-0.5 text-xs leading-5 text-muted">Controls whether conversations are persisted.</p>
                </div>
              </div>

              <div className="rounded-xl border border-border/70 bg-surface/35 p-1">
                <div className="grid grid-cols-2 gap-1">
                  <button
                    type="button"
                    disabled={updateAgent.isPending}
                    onClick={() => void updateSessionMode('stateful')}
                    className={cn(
                      'rounded-lg px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                      sessionMode === 'stateful' ? 'bg-primary/10 text-white ring-1 ring-primary/25' : 'text-muted hover:bg-background/50 hover:text-white',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold">Stateful</span>
                      {sessionMode === 'stateful' && <Check className="h-3.5 w-3.5 text-primary-light" />}
                    </div>
                    <p className="mt-1 text-[11px] leading-4 text-muted">Save session history.</p>
                  </button>

                  <button
                    type="button"
                    disabled={updateAgent.isPending}
                    onClick={() => void updateSessionMode('stateless')}
                    className={cn(
                      'rounded-lg px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                      sessionMode === 'stateless' ? 'bg-primary/10 text-white ring-1 ring-primary/25' : 'text-muted hover:bg-background/50 hover:text-white',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold">Stateless</span>
                      {sessionMode === 'stateless' && <Check className="h-3.5 w-3.5 text-primary-light" />}
                    </div>
                    <p className="mt-1 text-[11px] leading-4 text-muted">Do not save history.</p>
                  </button>
                </div>
              </div>
            </section>

            <p className="px-1 text-[11px] leading-4 text-muted/80">These controls are global agent settings, not draft or release snapshot fields.</p>
          </div>
        </div>
      )}
    </div>
  )
}
