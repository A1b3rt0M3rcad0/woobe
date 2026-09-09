import { useId } from 'react'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'

export function AgentDetailsSettings() {
  const { state, setField } = useAgentEditor()
  const id = useId()

  return (
    <div className="p-4">
      <div className="mb-5">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted">Agent details</p>
        <p className="mt-1 text-xs leading-5 text-muted">Define this Agent's identity, role and specialization.</p>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-muted" htmlFor={`${id}-name`}>Name</label>
          <Input id={`${id}-name`} value={state.name} onChange={event => setField('name', event.target.value)} />
        </div>

        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-muted" htmlFor={`${id}-description`}>Description</label>
          <Textarea
            id={`${id}-description`}
            rows={3}
            className="min-h-0 resize-y text-xs leading-5"
            value={state.description}
            onChange={event => setField('description', event.target.value)}
            placeholder="Role and specialization"
          />
        </div>
      </div>
    </div>
  )
}
