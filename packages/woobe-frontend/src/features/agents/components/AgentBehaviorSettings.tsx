import { useState } from 'react'
import { CircleHelp, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { behaviorFields, type AgentBehavior } from '../behavior'
import { AgentBehaviorFieldDialog } from './AgentBehaviorFieldDialog'

interface AgentBehaviorFieldsProps {
  behavior: AgentBehavior
  onChange: (behavior: AgentBehavior) => void
  agentName?: string
}

export function AgentBehaviorFields({ behavior, onChange, agentName = 'Agent' }: AgentBehaviorFieldsProps) {
  const [editing, setEditing] = useState<(typeof behaviorFields)[number] | null>(null)

  return (
    <section aria-label="Behavior" className="rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-3 p-4">
        <SlidersHorizontal className="h-4 w-4 shrink-0 text-primary" />
        <span className="text-sm font-semibold">Behavior</span>
      </div>
      <div className="divide-y divide-border border-t border-border">
        {behaviorFields.map(field => {
          const value = behavior[field.key]
          const isList = Array.isArray(value)
          const configured = isList ? value.filter(text => text.trim()).length : value.trim().length
          const summary = isList ? `${configured} configured` : field.key === 'objective' ? value || 'Not configured' : configured ? 'Configured' : 'Not configured'
          const action = isList ? 'Manage' : configured ? 'Edit' : 'Configure'
          return (
            <div key={field.key} className="flex h-16 items-center justify-between gap-2 px-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-xs font-medium text-white">{field.label}</span>
                  <span tabIndex={0} title={field.help} aria-label={`${field.label}: ${field.help}`} className="inline-flex shrink-0 cursor-help text-muted hover:text-primary-light"><CircleHelp className="h-3.5 w-3.5" aria-hidden="true" /></span>
                </div>
                <p className="mt-1 truncate text-[11px] text-muted">{summary}</p>
              </div>
              <Button type="button" size="sm" variant="ghost" className="shrink-0 px-2 text-[11px] text-primary-light" aria-label={`${action} ${field.label}`} onClick={() => setEditing(field)}>{action}</Button>
            </div>
          )
        })}
      </div>
      {editing ? <AgentBehaviorFieldDialog key={editing.key} field={editing} value={behavior[editing.key]} agentName={agentName} onApply={value => onChange({ ...behavior, [editing.key]: value })} onClose={() => setEditing(null)} /> : null}
    </section>
  )
}

export function AgentBehaviorSettings() {
  const { state, setField } = useAgentEditor()
  return <div className="p-4"><AgentBehaviorFields behavior={state.behavior} agentName={state.name} onChange={value => setField('behavior', value)} /></div>
}
