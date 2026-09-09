import { useId, useState } from 'react'
import { Ban, CheckCircle2, CircleHelp, Plus, SlidersHorizontal, Trash2 } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { behaviorFields, type AgentBehavior } from '../behavior'
import { cn } from '@/lib/utils'

type ListBehaviorKey = 'responsibilities' | 'allowedBehaviors' | 'disallowedBehaviors'
type GuidanceKey = 'operatingInstructions' | 'responseGuidelines' | 'additionalInstructions'

function fieldDefinition(key: keyof AgentBehavior) {
  return behaviorFields.find(field => field.key === key)!
}

function HelpHint({ label, help }: { label: string; help: string }) {
  return (
    <span
      tabIndex={0}
      title={help}
      aria-label={`${label}: ${help}`}
      className="inline-flex cursor-help items-center text-muted transition-colors hover:text-primary-light focus:text-primary-light focus:outline-none"
    >
      <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
    </span>
  )
}

function ListSetting({
  behavior,
  onChange,
  fieldKey,
  addLabel,
  tone = 'neutral',
}: {
  behavior: AgentBehavior
  onChange: (behavior: AgentBehavior) => void
  fieldKey: ListBehaviorKey
  addLabel: string
  tone?: 'neutral' | 'allowed' | 'disallowed'
}) {
  const definition = fieldDefinition(fieldKey)
  const items = behavior[fieldKey]
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState('')
  const configured = items.filter(item => item.trim()).length

  const confirmAdd = () => {
    if (!draft.trim()) return
    onChange({ ...behavior, [fieldKey]: [...items, draft] })
    setDraft('')
    setAdding(false)
  }

  const cancelAdd = () => {
    setDraft('')
    setAdding(false)
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-white">{definition.label}</span>
            <HelpHint label={definition.label} help={definition.help} />
          </div>
          <p className="mt-0.5 text-[10px] text-muted">{configured ? `${configured} configured` : `No ${definition.label.toLowerCase()} configured.`}</p>
        </div>
      </div>

      {items.length ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={index} className="rounded-lg border border-border bg-background/35 p-2.5">
              <div className="flex items-center gap-2">
                {tone === 'allowed' ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : null}
                {tone === 'disallowed' ? <Ban className="h-3.5 w-3.5 shrink-0 text-red-400" /> : null}
                {tone === 'neutral' ? <span className="w-5 shrink-0 font-mono text-[9px] text-muted/70">{String(index + 1).padStart(2, '0')}</span> : null}
                <Input
                  aria-label={`${definition.label} ${index + 1}`}
                  value={item}
                  onChange={event => onChange({ ...behavior, [fieldKey]: items.map((current, itemIndex) => itemIndex === index ? event.target.value : current) })}
                  className="h-8 min-w-0 flex-1 text-xs"
                />
                <button
                  type="button"
                  aria-label={`Remove ${definition.label.toLowerCase()} ${index + 1}`}
                  className="rounded-md p-1.5 text-muted transition-colors hover:bg-accent hover:text-red-400"
                  onClick={() => onChange({ ...behavior, [fieldKey]: items.filter((_, itemIndex) => itemIndex !== index) })}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {adding ? (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
          <Input
            autoFocus
            aria-label={`New ${definition.label}`}
            value={draft}
            onChange={event => setDraft(event.target.value)}
            placeholder={fieldKey === 'responsibilities' ? 'Describe a responsibility...' : 'Describe a behavior...'}
            className="text-xs"
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" size="sm" variant="ghost" className="h-7 text-[10px]" aria-label={`Cancel add ${definition.label.toLowerCase()}`} onClick={cancelAdd}>Cancel</Button>
            <Button type="button" size="sm" className="h-7 text-[10px]" aria-label={`Confirm add ${definition.label.toLowerCase()}`} disabled={!draft.trim()} onClick={confirmAdd}>Add</Button>
          </div>
        </div>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full justify-center text-[11px]"
          aria-label={`Add ${definition.label.toLowerCase()}`}
          onClick={() => setAdding(true)}
        >
          <Plus className="mr-1 h-3.5 w-3.5" />
          {addLabel}
        </Button>
      )}
    </div>
  )
}

function GuidanceSetting({
  behavior,
  onChange,
  fieldKey,
  description,
}: {
  behavior: AgentBehavior
  onChange: (behavior: AgentBehavior) => void
  fieldKey: GuidanceKey
  description: string
}) {
  const definition = fieldDefinition(fieldKey)
  const value = behavior[fieldKey]
  const configured = value.trim().length > 0
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  const beginEdit = () => {
    setDraft(value)
    setEditing(true)
  }

  const cancelEdit = () => {
    setDraft(value)
    setEditing(false)
  }

  const apply = () => {
    onChange({ ...behavior, [fieldKey]: draft })
    setEditing(false)
  }

  return (
    <div className="border-t border-border first:border-t-0">
      <div className="flex items-start justify-between gap-3 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-white">{definition.label}</span>
            <HelpHint label={definition.label} help={definition.help} />
          </div>
          <p className="mt-0.5 text-[10px] leading-4 text-muted">{description}</p>
          <span className={cn('mt-1 block font-mono text-[9px]', configured ? 'text-primary-light' : 'text-muted/60')}>
            {configured ? 'Configured' : 'Not configured'}
          </span>
        </div>
        {!editing ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 shrink-0 px-2 text-[10px] text-primary-light"
            aria-label={`${configured ? 'Edit' : 'Configure'} ${definition.label}`}
            onClick={beginEdit}
          >
            {configured ? 'Edit' : 'Configure'}
          </Button>
        ) : null}
      </div>

      {editing ? (
        <div className="pb-3">
          <label className="sr-only" htmlFor={`guidance-${fieldKey}`}>{definition.label}</label>
          <Textarea
            id={`guidance-${fieldKey}`}
            aria-label={definition.label}
            value={draft}
            onChange={event => setDraft(event.target.value)}
            rows={fieldKey === 'responseGuidelines' ? 4 : 5}
            className="min-h-0 resize-y text-xs leading-5"
            placeholder={definition.help}
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" size="sm" variant="ghost" className="h-7 text-[10px]" aria-label={`Cancel ${definition.label}`} onClick={cancelEdit}>Cancel</Button>
            <Button type="button" size="sm" className="h-7 text-[10px]" aria-label={`Apply ${definition.label}`} onClick={apply}>Apply</Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export function AgentBehaviorFields({ behavior, onChange }: { behavior: AgentBehavior; onChange: (behavior: AgentBehavior) => void }) {
  const id = useId()
  const objective = fieldDefinition('objective')
  const responsibilities = behavior.responsibilities.filter(item => item.trim()).length
  const rules = behavior.allowedBehaviors.filter(item => item.trim()).length + behavior.disallowedBehaviors.filter(item => item.trim()).length
  const guidance = [behavior.operatingInstructions, behavior.responseGuidelines, behavior.additionalInstructions].filter(item => item.trim()).length
  const configured = Boolean(behavior.objective.trim() || responsibilities || rules || guidance)

  return (
    <section aria-label="Behavior" className="rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-3 p-4">
        <SlidersHorizontal className="h-4 w-4 shrink-0 text-primary" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold">Behavior</span>
          <span className="mt-0.5 block text-[11px] text-muted">{configured ? `${responsibilities} responsibilities · ${rules} rules · ${guidance}/3 guidance` : 'Not configured'}</span>
        </span>
      </div>

      <div className="space-y-5 border-t border-border p-4">
        <p className="text-xs leading-5 text-muted">Define how this Agent operates, what it is responsible for and the boundaries it must respect.</p>

        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <label htmlFor={`${id}-objective`} className="text-xs font-medium text-white">{objective.label}</label>
            <HelpHint label={objective.label} help={objective.help} />
          </div>
          <p className="text-[10px] leading-4 text-muted">Primary outcome this Agent should pursue.</p>
          <Textarea
            id={`${id}-objective`}
            value={behavior.objective}
            onChange={event => onChange({ ...behavior, objective: event.target.value })}
            rows={4}
            className="min-h-0 resize-y text-xs leading-5"
            placeholder="Describe the primary outcome this Agent should achieve..."
          />
        </div>

        <div className="border-t border-border pt-5">
          <ListSetting behavior={behavior} onChange={onChange} fieldKey="responsibilities" addLabel="Add responsibility" />
        </div>

        <div className="border-t border-border pt-5">
          <div className="mb-3">
            <h4 className="text-xs font-semibold text-white">Behavior Rules</h4>
            <p className="mt-0.5 text-[10px] leading-4 text-muted">Make allowed and disallowed behavior explicit.</p>
          </div>
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-background/20 p-3">
              <ListSetting behavior={behavior} onChange={onChange} fieldKey="allowedBehaviors" addLabel="Add allowed behavior" tone="allowed" />
            </div>
            <div className="rounded-lg border border-border bg-background/20 p-3">
              <ListSetting behavior={behavior} onChange={onChange} fieldKey="disallowedBehaviors" addLabel="Add disallowed behavior" tone="disallowed" />
            </div>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <div className="mb-2">
            <h4 className="text-xs font-semibold text-white">Guidance</h4>
            <p className="mt-0.5 text-[10px] leading-4 text-muted">Configure detailed execution and response guidance only when needed.</p>
          </div>
          <div className="overflow-hidden rounded-lg border border-border px-3">
            <GuidanceSetting behavior={behavior} onChange={onChange} fieldKey="operatingInstructions" description="Specific guidance used while executing tasks." />
            <GuidanceSetting behavior={behavior} onChange={onChange} fieldKey="responseGuidelines" description="Tone, structure and presentation expectations." />
            <GuidanceSetting behavior={behavior} onChange={onChange} fieldKey="additionalInstructions" description="Additional guidance, including instructions preserved from legacy Agents." />
          </div>
        </div>
      </div>
    </section>
  )
}

export function AgentBehaviorSettings() {
  const { state, setField } = useAgentEditor()
  return <div className="p-4"><AgentBehaviorFields behavior={state.behavior} onChange={value => setField('behavior', value)} /></div>
}
