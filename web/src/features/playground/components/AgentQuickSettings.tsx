import { useState, useEffect } from 'react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'

interface AgentQuickSettingsProps {
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

export function AgentQuickSettings({ agent }: AgentQuickSettingsProps) {
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
      })
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
    <Card>
      <CardContent className="p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Name</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Description</label>
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">System Prompt</label>
          <Textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="min-h-[120px] font-mono text-sm"
            placeholder="You are a helpful AI assistant..."
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-muted mb-1">Session Mode</label>
            <Select value={sessionMode} onChange={(e) => setSessionMode(e.target.value)} options={sessionModes} />
          </div>
          <div>
            <label className="block text-sm font-medium text-muted mb-1">Status</label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} options={statusOptions} />
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Button size="sm" onClick={handleSave} disabled={!hasChanges} loading={updateAgent.isPending}>
            Save Changes
          </Button>
          <Button size="sm" variant="outline" onClick={handleReset} disabled={!hasChanges}>
            Reset
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
