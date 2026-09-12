import { Field, FieldDescription, FieldLabel } from '@woobe/ui'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'

interface AgentDetailsStepProps { flow: AgentCreationFlowController }

export function AgentDetailsStep({ flow }: AgentDetailsStepProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Field><FieldLabel>Name</FieldLabel><Input value={flow.agentName} onChange={(event) => flow.setAgentName(event.target.value)} placeholder="Customer Support Agent" autoFocus /></Field>
        <Field><FieldLabel>Description <span className="font-normal text-muted">(optional)</span></FieldLabel><Input value={flow.agentDescription} onChange={(event) => flow.setAgentDescription(event.target.value)} placeholder="Handles customer questions and support requests" /></Field>
      </div>
      <Field>
        <FieldLabel>Objective</FieldLabel>
        <Textarea value={flow.agentObjective} onChange={(event) => flow.setAgentObjective(event.target.value)} aria-label="Objective" rows={4} placeholder="Resolve customer support requests accurately." className="min-h-24 resize-y" />
        <FieldDescription>This objective initializes the Behavior. Configure the full Behavior in the Agent editor.</FieldDescription>
      </Field>
    </div>
  )
}
