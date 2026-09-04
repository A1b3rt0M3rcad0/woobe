import { AgentContextAssemblerField } from '@/features/agents/components/AgentContextAssemblerField'
import { AgentSessionModeField } from '@/features/agents/components/AgentSessionModeField'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useAgentEditor } from '../AgentEditorContext'

export function AgentSettingsTab() {
  const { state, setField } = useAgentEditor()

  return (
    <div className="p-4 space-y-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Agent Details</p>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Name</label>
            <Input value={state.name} onChange={(e) => setField('name', e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Description</label>
            <Input value={state.description} onChange={(e) => setField('description', e.target.value)} placeholder="Optional description" />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">System Prompt</p>
          <Textarea
            value={state.systemPrompt}
            onChange={(e) => setField('systemPrompt', e.target.value)}
            className="min-h-[160px] font-mono text-xs leading-relaxed"
            placeholder="System instructions..."
          />
        </div>
      </div>

      <AgentContextAssemblerField />
      <AgentSessionModeField />
    </div>
  )
}
