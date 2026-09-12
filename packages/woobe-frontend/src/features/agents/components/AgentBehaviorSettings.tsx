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
    <section aria-label="Behavior" className="rounded-container border border-border bg-surface/[0.72]">
      <div className="flex items-start gap-2.5 border-b border-border p-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><SlidersHorizontal className="h-3.5 w-3.5" /></span>
        <div className="min-w-0"><p className="font-mono text-[9px] font-bold text-slate-50">Behavior</p><p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">Objective, responsibilities, behavioral limits and operating guidance.</p></div>
      </div>
      <div className="divide-y divide-border/60">
        {behaviorFields.map(field => {
          const value = behavior[field.key]
          const isList = Array.isArray(value)
          const configured = isList ? value.filter(text => text.trim()).length : value.trim().length
          const summary = isList ? `${configured} configured` : field.key === 'objective' ? value || 'Not configured' : configured ? 'Configured' : 'Not configured'
          const action = isList ? 'Manage' : configured ? 'Edit' : 'Configure'
          return (
            <div key={field.key} className="flex min-h-[48px] items-center justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5"><span className="truncate font-mono text-[9px] font-semibold text-slate-100">{field.label}</span><span tabIndex={0} title={field.help} aria-label={`${field.label}: ${field.help}`} className="inline-flex shrink-0 cursor-help text-muted-foreground hover:text-primary-light"><CircleHelp className="h-3 w-3" aria-hidden="true" /></span></div>
                <p className="mt-1 truncate font-sans text-[9px] text-muted-foreground">{summary}</p>
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
  return <div className="p-3"><AgentBehaviorFields behavior={state.behavior} agentName={state.name} onChange={value => setField('behavior', value)} /></div>
}
