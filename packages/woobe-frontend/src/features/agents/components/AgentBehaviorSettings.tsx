import { useState } from 'react'
import { CircleHelp, SlidersHorizontal } from 'lucide-react'
import { PanelHeader } from '@woobe/ui'
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
    <section aria-label="Behavior" className="rounded-container border border-border bg-surface/[0.72]">
      <PanelHeader icon={<SlidersHorizontal className="h-3.5 w-3.5" />} title="Behavior" description="Objective, responsibilities, behavioral limits and operating guidance." />
      <div className="divide-y divide-border/60">
        {behaviorFields.map(field => {
          const value = behavior[field.key]
          const isList = Array.isArray(value)
          const configured = isList ? value.filter(text => text.trim()).length : value.trim().length
          const summary = isList ? `${configured} configured` : field.key === 'objective' ? value || 'Not configured' : configured ? 'Configured' : 'Not configured'
          const action = isList ? 'Manage' : configured ? 'Edit' : 'Configure'
          return (
            <div key={field.key} className="flex min-h-panel-header items-center justify-between gap-ui-md px-ui-md py-ui-sm">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-ui-xs"><span className="truncate font-mono text-system-label font-semibold text-slate-100">{field.label}</span><span tabIndex={0} title={field.help} aria-label={`${field.label}: ${field.help}`} className="inline-flex shrink-0 cursor-help text-muted-foreground hover:text-primary-light"><CircleHelp className="h-3 w-3" aria-hidden="true" /></span></div>
                <p className="mt-ui-xs truncate font-sans text-product-caption text-muted-foreground">{summary}</p>
              </div>
              <Button type="button" size="sm" variant="ghost" className="shrink-0 text-primary-light" aria-label={`${action} ${field.label}`} onClick={() => setEditing(field)}>{action}</Button>
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
  return <div className="p-ui-md"><AgentBehaviorFields behavior={state.behavior} agentName={state.name} onChange={value => setField('behavior', value)} /></div>
}
