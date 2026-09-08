import { AgentContextAssemblerField } from '@/features/agents/components/AgentContextAssemblerField'
import { AgentSessionModeField } from '@/features/agents/components/AgentSessionModeField'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'

export function NetworkAgentFields({ projectId }: { projectId: string }) {
  const { state, setField } = useAgentEditor()
  return (
    <div className="space-y-4 p-4">
      <AgentContextAssemblerField projectId={projectId} />
      <section className="rounded-xl border border-border bg-surface p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Agent Details</p>
        <div className="space-y-3">
          <label className="block text-xs font-medium text-muted">Name<Input className="mt-1" value={state.name} onChange={(event) => setField('name', event.target.value)} /></label>
          <label className="block text-xs font-medium text-muted">Description<Input className="mt-1" value={state.description} onChange={(event) => setField('description', event.target.value)} placeholder="Optional description" /></label>
        </div>
      </section>
      <section className="rounded-xl border border-border bg-surface p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">System Prompt</p>
        <Textarea value={state.systemPrompt} onChange={(event) => setField('systemPrompt', event.target.value)} className="min-h-[160px] resize-y font-mono text-xs leading-relaxed" placeholder="System instructions..." />
      </section>
      <AgentSessionModeField />
    </div>
  )
}
