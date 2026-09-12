import { useId } from 'react'
import { Bot, SlidersHorizontal } from 'lucide-react'
import { PanelHeader } from '@woobe/ui'
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
  const guidance = [behavior.operatingInstructions, behavior.responseGuidelines, behavior.additionalInstructions].filter(item => item.trim()).length
  const objective = behavior.objective.trim()
  const configured = Boolean(objective || responsibilities || allowed || disallowed || guidance)

  return (
    <div className="space-y-ui-md p-ui-md">
      <section className="rounded-container border border-border bg-surface/[0.72]" aria-label="Agent Identity">
        <PanelHeader icon={<Bot className="h-3.5 w-3.5" />} title="Agent identity" description="Name, role and specialization used to identify this Agent." />
        <div className="space-y-ui-md p-ui-md">
          <div className="space-y-ui-sm">
            <label className="block font-mono text-system-meta font-medium uppercase tracking-[0.1em] text-muted-foreground" htmlFor={`${id}-name`}>Name</label>
            <Input id={`${id}-name`} value={state.name} onChange={event => setField('name', event.target.value)} />
          </div>
          <div className="space-y-ui-sm">
            <label className="block font-mono text-system-meta font-medium uppercase tracking-[0.1em] text-muted-foreground" htmlFor={`${id}-description`}>Description</label>
            <Textarea id={`${id}-description`} rows={2} className="min-h-[78px] resize-y font-sans text-product-small" value={state.description} onChange={event => setField('description', event.target.value)} placeholder="Role and specialization" />
          </div>
        </div>
      </section>

      <section className="rounded-container border border-border bg-surface/[0.72]" aria-label="Behavior Summary">
        <PanelHeader icon={<SlidersHorizontal className="h-3.5 w-3.5" />} title="Behavior" description={configured ? `${responsibilities} responsibilities · ${allowed + disallowed} rules` : 'Not configured'} />
        <div className="space-y-ui-md p-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">Define the Agent objective, responsibilities, behavioral limits and operating guidance.</p>

          {objective ? (
            <div className="rounded-container border border-border bg-background/25 p-ui-md">
              <span className="block font-mono text-system-meta uppercase tracking-[0.1em] text-muted-foreground">Objective</span>
              <p className="mt-ui-xs line-clamp-2 font-sans text-system-control text-slate-100">{objective}</p>
            </div>
          ) : null}

          <div className="divide-y divide-border/60 overflow-hidden rounded-container border border-border bg-background/20">
            {[
              ['Objective', objective ? 'Configured' : 'Not set'],
              ['Responsibilities', String(responsibilities)],
              ['Behavior rules', String(allowed + disallowed)],
              ['Guidance', `${guidance} / 3`],
            ].map(([label, value]) => (
              <div key={label} className="flex min-h-control items-center justify-between gap-ui-md px-ui-md py-ui-sm">
                <span className="font-sans text-product-caption text-muted-foreground">{label}</span>
                <span className="font-mono text-system-meta text-slate-300">{value}</span>
              </div>
            ))}
          </div>

          <Button type="button" size="sm" variant="outline" className="w-full" onClick={() => onOpenBehavior?.()}>
            {configured ? 'Edit Behavior' : 'Configure Behavior'}
          </Button>
        </div>
      </section>
    </div>
  )
}
