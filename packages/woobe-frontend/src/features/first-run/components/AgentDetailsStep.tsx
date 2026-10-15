import { useId } from 'react'
import { Button, Field, FieldDescription, FieldError, FieldLabel, Input, Textarea } from '@woobe/ui'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'

interface AgentDetailsStepProps { flow: AgentCreationFlowController }

export function AgentDetailsStep({ flow }: AgentDetailsStepProps) {
  const id = useId()
  const nameError = !flow.agentName.trim() ? flow.detailsErrors.name : undefined
  const objectiveError = !flow.agentObjective.trim() ? flow.detailsErrors.objective : undefined
  return (
    <div className="space-y-6">
      <Field>
        <FieldLabel htmlFor={`${id}-name`}>Agent name <span className="font-normal text-muted">(required)</span></FieldLabel>
        <Input id={`${id}-name`} value={flow.agentName} onChange={event => flow.setAgentName(event.target.value)} invalid={!!nameError} required aria-describedby={nameError ? `${id}-name-error ${id}-name-help` : `${id}-name-help`} placeholder="e.g. Customer Support" autoFocus autoComplete="off" />
        {nameError && <FieldError id={`${id}-name-error`}>{nameError}</FieldError>}
        <FieldDescription id={`${id}-name-help`} className="text-sm leading-5">A name you will recognize in your Project and Run history.</FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor={`${id}-objective`}>What should this Agent do? <span className="font-normal text-muted">(required)</span></FieldLabel>
        <Textarea id={`${id}-objective`} value={flow.agentObjective} onChange={event => flow.setAgentObjective(event.target.value)} invalid={!!objectiveError} required aria-describedby={objectiveError ? `${id}-objective-error ${id}-objective-help` : `${id}-objective-help`} rows={5} placeholder="Describe its goal, how it should help and what it should avoid." className="min-h-32 resize-y" />
        {objectiveError && <FieldError id={`${id}-objective-error`}>{objectiveError}</FieldError>}
        <FieldDescription id={`${id}-objective-help`} className="text-sm leading-5">This becomes the Agent’s objective. You can add responsibilities and rules in the Playground.</FieldDescription>
        {!flow.agentObjective.trim() && <div><Button type="button" size="sm" variant="ghost" onClick={() => {
          if (!flow.agentName.trim()) flow.setAgentName('Customer Support')
          flow.setAgentObjective('Help customers investigate product issues. Ask for missing details, suggest clear next steps and say when you cannot verify an answer. Never invent account information.')
        }}>Use a customer support example</Button></div>}
      </Field>
      <Field>
        <FieldLabel htmlFor={`${id}-description`}>Description <span className="font-normal text-muted">(optional)</span></FieldLabel>
        <Input id={`${id}-description`} value={flow.agentDescription} onChange={event => flow.setAgentDescription(event.target.value)} aria-describedby={`${id}-description-help`} placeholder="A short summary for your team" />
        <FieldDescription id={`${id}-description-help`} className="text-sm leading-5">Helps your team identify the Agent. It does not change its behavior.</FieldDescription>
      </Field>
    </div>
  )
}
