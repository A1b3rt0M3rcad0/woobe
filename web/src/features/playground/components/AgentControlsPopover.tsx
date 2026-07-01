import { useEffect, useState } from 'react'
import { Activity, Database, Power, PowerOff, SlidersHorizontal, X } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Select'
import { useUpdateAgent } from '@/features/agents/hooks'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { Agent } from '@/features/agents/types'

type RuntimeStatus = 'active' | 'inactive'
type RuntimeSessionMode = 'stateful' | 'stateless'

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

const sessionModeOptions = [
  { value: 'stateful', label: 'Stateful' },
  { value: 'stateless', label: 'Stateless' },
]

function normalizeStatus(value?: string): RuntimeStatus {
  return value === 'inactive' ? 'inactive' : 'active'
}

function normalizeSessionMode(value?: string): RuntimeSessionMode {
  return value === 'stateless' ? 'stateless' : 'stateful'
}

export function AgentControlsPopover({ agent }: { agent: Agent }) {
  const updateAgent = useUpdateAgent(agent.id)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<RuntimeStatus>(normalizeStatus(agent.status))
  const [sessionMode, setSessionMode] = useState<RuntimeSessionMode>(normalizeSessionMode(agent.session_mode))

  useEffect(() => {
    setStatus(normalizeStatus(agent.status))
    setSessionMode(normalizeSessionMode(agent.session_mode))
  }, [agent.status, agent.session_mode])

  async function updateStatus(nextStatus: RuntimeStatus) {
    setStatus(nextStatus)
    try {
      await updateAgent.mutateAsync({ status: nextStatus })
      toast.success(nextStatus === 'active' ? 'Agent activated' : 'Agent deactivated')
    } catch (error) {
      setStatus(normalizeStatus(agent.status))
      toast.error(error instanceof Error ? error.message : 'Failed to update agent status')
    }
  }

  async function updateSessionMode(nextMode: RuntimeSessionMode) {
    setSessionMode(nextMode)
    try {
      await updateAgent.mutateAsync({ session_mode: nextMode })
      toast.success(nextMode === 'stateful' ? 'Agent set to stateful mode' : 'Agent set to stateless mode')
    } catch (error) {
      setSessionMode(normalizeSessionMode(agent.session_mode))
      toast.error(error instanceof Error ? error.message : 'Failed to update session mode')
    }
  }

  return (
    <div className="relative flex items-center gap-2">
      <button type="button" onClick={() => setOpen(true)} className="shrink-0" title="Open global agent controls">
        <Badge variant={status === 'active' ? 'success' : 'secondary'} className="capitalize cursor-pointer">
          {status === 'active' ? 'Active' : 'Inactive'}
        </Badge>
      </button>
      <button type="button" onClick={() => setOpen(true)} className="shrink-0" title="Open global agent controls">
        <Badge variant={sessionMode === 'stateful' ? 'secondary' : 'default'} className="capitalize cursor-pointer">
          {sessionMode === 'stateful' ? 'Stateful' : 'Stateless'}
        </Badge>
      </button>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'hidden h-7 items-center gap-1.5 rounded-lg border px-2 text-[11px] font-medium transition-colors lg:inline-flex',
          open ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-border/80 bg-background/45 text-muted hover:border-primary/30 hover:bg-primary/5 hover:text-white',
        )}
      >
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Agent Controls
      </button>

      {open && (
        <div className="absolute left-0 top-9 z-50 w-[360px] overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40 backdrop-blur-md">
          <div className="flex items-start justify-between gap-3 border-b border-border/90 bg-background/25 p-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Agent Controls</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Global settings for this agent. They affect Playground, API, Staging and Production, and are not part of release snapshots.
              </p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-transparent p-1 text-muted hover:border-border/80 hover:bg-background/60 hover:text-white">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-3 p-4">
            <section className="rounded-xl border border-border/80 bg-background/45 p-3">
              <div className="mb-3 flex items-center gap-2">
                {status === 'active' ? <Power className="h-4 w-4 text-emerald-400" /> : <PowerOff className="h-4 w-4 text-muted" />}
                <div>
                  <p className="text-sm font-medium text-white">Agent availability</p>
                  <p className="text-xs leading-5 text-muted">Inactive agents cannot execute anywhere.</p>
                </div>
              </div>
              <Select value={status} onChange={(event) => void updateStatus(event.target.value as RuntimeStatus)} options={statusOptions} disabled={updateAgent.isPending} />
            </section>

            <section className="rounded-xl border border-border/80 bg-background/45 p-3">
              <div className="mb-3 flex items-center gap-2">
                {sessionMode === 'stateful' ? <Database className="h-4 w-4 text-primary-light" /> : <Activity className="h-4 w-4 text-muted" />}
                <div>
                  <p className="text-sm font-medium text-white">Session persistence</p>
                  <p className="text-xs leading-5 text-muted">Stateless agents ignore session IDs and do not persist conversations.</p>
                </div>
              </div>
              <Select value={sessionMode} onChange={(event) => void updateSessionMode(event.target.value as RuntimeSessionMode)} options={sessionModeOptions} disabled={updateAgent.isPending} />
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
