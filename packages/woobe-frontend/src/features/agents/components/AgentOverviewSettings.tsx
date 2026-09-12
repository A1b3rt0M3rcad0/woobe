import { useId } from 'react'
import { Bot, SlidersHorizontal } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'

interface AgentOverviewSettingsProps {
  onOpenBehavior?: () => void
}

function SectionHeader({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex items-start gap-2.5 border-b border-border px-3 py-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">{icon}</span>
      <div className="min-w-0">
        <p className="font-mono text-[9px] font-bold text-slate-50">{title}</p>
        <p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">{description}</p>
      </div>
    </div>
  )
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
    <div className="space-y-3 p-3">
      <section className="rounded-container border border-border bg-surface/[0.72]" aria-label="Agent Identity">
        <SectionHeader icon={<Bot className="h-3.5 w-3.5" />} title="Agent identity" description="Name, role and specialization used to identify this Agent." />
        <div className="space-y-3 p-3">
          <div className="space-y-1.5">
            <label className="block font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground" htmlFor={`${id}-name`}>Name</label>
            <Input id={`${id}-name`} value={state.name} onChange={event => setField('name', event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="block font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground" htmlFor={`${id}-description`}>Description</label>
            <Textarea id={`${id}-description`} rows={2} className="min-h-[78px] resize-y font-sans text-[11px] leading-4" value={state.description} onChange={event => setField('description', event.target.value)} placeholder="Role and specialization" />
          </div>
        </div>
      </section>

      <section className="rounded-container border border-border bg-surface/[0.72]" aria-label="Behavior Summary">
        <SectionHeader icon={<SlidersHorizontal className="h-3.5 w-3.5" />} title="Behavior" description={configured ? `${responsibilities} responsibilities · ${allowed + disallowed} rules` : 'Not configured'} />
        <div className="space-y-3 p-3">
          <p className="font-sans text-[9px] leading-4 text-muted-foreground">Define the Agent objective, responsibilities, behavioral limits and operating guidance.</p>

          {objective ? (
            <div className="rounded-container border border-border bg-background/25 p-3">
              <span className="block font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Objective</span>
              <p className="mt-1 line-clamp-2 font-sans text-[10px] leading-4 text-slate-100">{objective}</p>
            </div>
          ) : null}

          <div className="divide-y divide-border/60 overflow-hidden rounded-container border border-border bg-background/20">
            {[
              ['Objective', objective ? 'Configured' : 'Not set'],
              ['Responsibilities', String(responsibilities)],
              ['Behavior rules', String(allowed + disallowed)],
              ['Guidance', `${guidance} / 3`],
            ].map(([label, value]) => (
              <div key={label} className="flex min-h-[34px] items-center justify-between gap-3 px-3 py-2">
                <span className="font-sans text-[9px] text-muted-foreground">{label}</span>
                <span className="font-mono text-[8px] text-slate-300">{value}</span>
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
