import { useId } from 'react'
import { Bot, SlidersHorizontal } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'

interface AgentOverviewSettingsProps {
  onOpenBehavior?: () => void
}

export function AgentOverviewSettings({ onOpenBehavior }: AgentOverviewSettingsProps) {
  const { state, setField } = useAgentEditor()
  const id = useId()
  const behavior = state.behavior
  const responsibilities = behavior.responsibilities.filter(item => item.trim()).length
  const allowed = behavior.allowedBehaviors.filter(item => item.trim()).length
  const disallowed = behavior.disallowedBehaviors.filter(item => item.trim()).length
  const guidance = [behavior.operatingInstructions, behavior.responseGuidelines, behavior.additionalInstructions]
    .filter(item => item.trim()).length
  const objective = behavior.objective.trim()
  const configured = Boolean(objective || responsibilities || allowed || disallowed || guidance)

  return (
    <div className="space-y-4 p-4">
      <section className="rounded-xl border border-border bg-surface" aria-label="Agent Identity">
        <div className="flex items-center gap-3 p-4">
          <Bot className="h-4 w-4 shrink-0 text-primary" />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">Agent Identity</span>
            <span className="mt-0.5 block text-[11px] text-muted">Name, role and specialization used to identify this Agent.</span>
          </span>
        </div>
        <div className="space-y-4 border-t border-border p-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-muted" htmlFor={`${id}-name`}>Name</label>
            <Input id={`${id}-name`} value={state.name} onChange={event => setField('name', event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-muted" htmlFor={`${id}-description`}>Description</label>
            <Textarea
              id={`${id}-description`}
              rows={2}
              className="min-h-0 resize-y text-xs leading-5"
              value={state.description}
              onChange={event => setField('description', event.target.value)}
              placeholder="Role and specialization"
            />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface" aria-label="Behavior Summary">
        <div className="flex items-center gap-3 p-4">
          <SlidersHorizontal className="h-4 w-4 shrink-0 text-primary" />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">Behavior</span>
            <span className="mt-0.5 block text-[11px] text-muted">{configured ? `${responsibilities} responsibilities · ${allowed + disallowed} rules` : 'Not configured'}</span>
          </span>
        </div>
        <div className="space-y-4 border-t border-border p-4">
          <p className="text-xs leading-5 text-muted">Define the Agent's objective, responsibilities, behavioral limits and operating guidance.</p>

          {objective ? (
            <div className="rounded-lg border border-border bg-background/35 p-3">
              <span className="block font-mono text-[9px] uppercase tracking-wider text-muted">Objective</span>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-white/90">{objective}</p>
            </div>
          ) : null}

          <div className="overflow-hidden rounded-lg border border-border">
            <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2.5">
              <span className="text-xs text-muted">Objective</span>
              <span className="font-mono text-[10px] text-muted">{objective ? 'Configured' : 'Not set'}</span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2.5">
              <span className="text-xs text-muted">Responsibilities</span>
              <span className="font-mono text-[10px] text-muted">{responsibilities}</span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2.5">
              <span className="text-xs text-muted">Behavior rules</span>
              <span className="font-mono text-[10px] text-muted">{allowed + disallowed}</span>
            </div>
            <div className="flex items-center justify-between gap-3 px-3 py-2.5">
              <span className="text-xs text-muted">Guidance</span>
              <span className="font-mono text-[10px] text-muted">{guidance} / 3</span>
            </div>
          </div>

          <Button type="button" size="sm" variant="outline" className="w-full" onClick={() => onOpenBehavior?.()}>
            {configured ? 'Edit Behavior' : 'Configure Behavior'}
          </Button>
        </div>
      </section>
    </div>
  )
}
