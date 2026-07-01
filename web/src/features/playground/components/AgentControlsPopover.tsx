import { useEffect, useRef, useState } from 'react'
import { Activity, Check, ChevronDown, Database, Power, PowerOff, SlidersHorizontal, X } from 'lucide-react'
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
  const memoryLabel = sessionMode === 'stateful' ? 'Memory on' : 'Memory off'

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
      toast.success(nextStatus === 'active' ? 'Agent turned on' : 'Agent turned off')
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
      toast.success(nextMode === 'stateful' ? 'Conversation memory enabled' : 'Conversation memory disabled')
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
          'inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium transition-colors',
          open
            ? 'border-primary/35 bg-primary/10 text-primary-light shadow-sm shadow-primary/5'
            : 'border-border/80 bg-background/55 text-muted hover:border-primary/35 hover:bg-primary/5 hover:text-white',
        )}
        title="Agent controls"
      >
        {isAgentOn ? <Power className="h-3.5 w-3.5 text-emerald-400" /> : <PowerOff className="h-3.5 w-3.5 text-muted" />}
        <span className="hidden xl:inline">Agent</span>
        <span className={cn('font-semibold', isAgentOn ? 'text-emerald-300' : 'text-slate-300')}>{isAgentOn ? 'On' : 'Off'}</span>
        <span className="hidden text-muted/70 2xl:inline">· {memoryLabel}</span>
        <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-[390px] overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40 backdrop-blur-md">
          <div className="flex items-start justify-between gap-3 border-b border-border/90 bg-background/25 p-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Agent Controls</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Global controls for this agent. Changes affect Playground, API, Staging and Production. They are not release snapshot fields.
              </p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-transparent p-1 text-muted hover:border-border/80 hover:bg-background/60 hover:text-white">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-3 p-4">
            <section className={cn('rounded-xl border p-3 transition-colors', isAgentOn ? 'border-emerald-500/25 bg-emerald-500/[0.06]' : 'border-border/80 bg-background/45')}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  {isAgentOn ? <Power className="h-4 w-4 shrink-0 text-emerald-400" /> : <PowerOff className="h-4 w-4 shrink-0 text-muted" />}
                  <div>
                    <p className="text-sm font-medium text-white">Agent execution</p>
                    <p className="text-xs leading-5 text-muted">
                      {isAgentOn ? 'The agent can run in Playground, API, Staging and Production.' : 'All executions are paused. Drafts and releases are preserved.'}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  aria-pressed={isAgentOn}
                  disabled={updateAgent.isPending}
                  onClick={() => void updateStatus(isAgentOn ? 'inactive' : 'active')}
                  className={cn(
                    'relative h-7 w-12 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                    isAgentOn ? 'border-emerald-400/50 bg-emerald-500/30' : 'border-border bg-background/70',
                  )}
                  title={isAgentOn ? 'Turn agent off' : 'Turn agent on'}
                >
                  <span className={cn('absolute top-1 h-5 w-5 rounded-full bg-white shadow-sm transition-transform', isAgentOn ? 'translate-x-5' : 'translate-x-1')} />
                </button>
              </div>
              <div className="rounded-lg border border-border/70 bg-background/35 px-3 py-2 text-[11px] text-muted">
                Current state: <span className={cn('font-medium', isAgentOn ? 'text-emerald-300' : 'text-slate-300')}>{isAgentOn ? 'On / executions enabled' : 'Off / executions blocked'}</span>
              </div>
            </section>

            <section className="rounded-xl border border-border/80 bg-background/45 p-3">
              <div className="mb-3 flex items-center gap-2">
                {sessionMode === 'stateful' ? <Database className="h-4 w-4 text-primary-light" /> : <Activity className="h-4 w-4 text-muted" />}
                <div>
                  <p className="text-sm font-medium text-white">Conversation memory</p>
                  <p className="text-xs leading-5 text-muted">Choose whether this agent should save conversation sessions.</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={updateAgent.isPending}
                  onClick={() => void updateSessionMode('stateful')}
                  className={cn(
                    'rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                    sessionMode === 'stateful' ? 'border-primary/40 bg-primary/10 text-white' : 'border-border/80 bg-surface/40 text-muted hover:border-primary/25 hover:bg-primary/5 hover:text-white',
                  )}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold">Save history</span>
                    {sessionMode === 'stateful' && <Check className="h-3.5 w-3.5 text-primary-light" />}
                  </div>
                  <p className="text-[11px] leading-4 text-muted">Creates sessions and keeps conversation context.</p>
                  <span className="mt-2 inline-flex rounded-md border border-border/70 px-1.5 py-0.5 text-[10px] text-muted">Stateful</span>
                </button>

                <button
                  type="button"
                  disabled={updateAgent.isPending}
                  onClick={() => void updateSessionMode('stateless')}
                  className={cn(
                    'rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                    sessionMode === 'stateless' ? 'border-primary/40 bg-primary/10 text-white' : 'border-border/80 bg-surface/40 text-muted hover:border-primary/25 hover:bg-primary/5 hover:text-white',
                  )}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold">Do not save</span>
                    {sessionMode === 'stateless' && <Check className="h-3.5 w-3.5 text-primary-light" />}
                  </div>
                  <p className="text-[11px] leading-4 text-muted">No session history. Ignores session IDs.</p>
                  <span className="mt-2 inline-flex rounded-md border border-border/70 px-1.5 py-0.5 text-[10px] text-muted">Stateless</span>
                </button>
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
