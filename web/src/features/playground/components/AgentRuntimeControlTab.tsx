import { useEffect, useState } from 'react'
import { Activity, Database, Power, PowerOff } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Select'
import { useUpdateAgent } from '@/features/agents/hooks'
import { toast } from 'sonner'
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

export function AgentRuntimeControlTab({ agent, agentId }: { agent: Agent; agentId: string }) {
  const updateAgent = useUpdateAgent(agentId)
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
    <div className="space-y-4 p-4">
      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Global Runtime Control</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              These settings belong to the agent itself and apply to draft, staging and production runtime.
            </p>
          </div>
          <Badge variant={status === 'active' ? 'success' : 'secondary'} className="shrink-0 capitalize">
            {status}
          </Badge>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 flex items-center gap-2">
          {status === 'active' ? <Power className="h-4 w-4 text-emerald-400" /> : <PowerOff className="h-4 w-4 text-muted" />}
          <div>
            <p className="text-sm font-medium text-white">Agent availability</p>
            <p className="text-xs leading-5 text-muted">Inactive agents cannot run in playground, staging or production.</p>
          </div>
        </div>
        <Select
          value={status}
          onChange={(event) => void updateStatus(event.target.value as RuntimeStatus)}
          options={statusOptions}
          disabled={updateAgent.isPending}
        />
      </section>

      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 flex items-center gap-2">
          {sessionMode === 'stateful' ? <Database className="h-4 w-4 text-primary-light" /> : <Activity className="h-4 w-4 text-muted" />}
          <div>
            <p className="text-sm font-medium text-white">Session persistence</p>
            <p className="text-xs leading-5 text-muted">
              Stateful agents persist session history. Stateless agents ignore session IDs and do not persist conversations.
            </p>
          </div>
        </div>
        <Select
          value={sessionMode}
          onChange={(event) => void updateSessionMode(event.target.value as RuntimeSessionMode)}
          options={sessionModeOptions}
          disabled={updateAgent.isPending}
        />
      </section>
    </div>
  )
}
