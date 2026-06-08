import { useState, useEffect } from 'react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Separator } from '@/components/ui/Separator'
import { Expand } from 'lucide-react'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'

interface AgentSettingsTabProps {
  agent: Agent
}

const sessionModes = [
  { value: 'stateless', label: 'Stateless' },
  { value: 'stateful', label: 'Stateful' },
]

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

export function AgentSettingsTab({ agent }: AgentSettingsTabProps) {
  const updateAgent = useUpdateAgent(agent.id)

  const [name, setName] = useState(agent.name)
  const [description, setDescription] = useState(agent.description || '')
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt || '')
  const [sessionMode, setSessionMode] = useState(agent.session_mode || 'stateful')
  const [status, setStatus] = useState(agent.status)

  useEffect(() => {
    setName(agent.name)
    setDescription(agent.description || '')
    setSystemPrompt(agent.system_prompt || '')
    setSessionMode(agent.session_mode || 'stateful')
    setStatus(agent.status)
  }, [agent])

  const hasChanges =
    name !== agent.name ||
    description !== (agent.description || '') ||
    systemPrompt !== (agent.system_prompt || '') ||
    sessionMode !== (agent.session_mode || 'stateful') ||
    status !== agent.status

  const handleSave = async () => {
    try {
      await updateAgent.mutateAsync({
        name,
        description,
        system_prompt: systemPrompt,
        session_mode: sessionMode,
        status,
      } as any)
      toast.success('Agent updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update agent')
    }
  }

  const handleReset = () => {
    setName(agent.name)
    setDescription(agent.description || '')
    setSystemPrompt(agent.system_prompt || '')
    setSessionMode(agent.session_mode || 'stateful')
    setStatus(agent.status)
  }

  return (
    <div className="p-4 space-y-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Agent Details</p>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Description</label>
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">System Prompt</p>
            <button
              className="flex items-center gap-1 text-xs text-muted hover:text-white transition-colors"
              title="Expand"
            >
              <Expand className="h-3 w-3" />
              Expand
            </button>
          </div>
          <Textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="min-h-[160px] font-mono text-xs leading-relaxed"
            placeholder="You are a helpful AI assistant..."
          />
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Runtime</p>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Session Mode</label>
            <Select value={sessionMode} onChange={(e) => setSessionMode(e.target.value)} options={sessionModes} />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Status</label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} options={statusOptions} />
          </div>
        </div>
      </div>

      {hasChanges && (
        <div className="flex items-center gap-2 px-1">
          <div className="flex-1">
            <p className="text-xs text-yellow-400">Unsaved changes</p>
          </div>
          <Button size="sm" variant="outline" onClick={handleReset}>
            Reset
          </Button>
          <Button size="sm" onClick={handleSave} loading={updateAgent.isPending}>
            Save Changes
          </Button>
        </div>
      )}
    </div>
  )
}
