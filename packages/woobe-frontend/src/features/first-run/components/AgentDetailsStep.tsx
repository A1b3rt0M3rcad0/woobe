import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'

interface AgentDetailsStepProps {
  flow: AgentCreationFlowController
}

export function AgentDetailsStep({ flow }: AgentDetailsStepProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">Name</label>
          <Input
            value={flow.agentName}
            onChange={(event) => flow.setAgentName(event.target.value)}
            placeholder="Customer Support Agent"
            autoFocus
            className="h-10"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">
            Description <span className="font-normal text-muted/70">(optional)</span>
          </label>
          <Input
            value={flow.agentDescription}
            onChange={(event) => flow.setAgentDescription(event.target.value)}
            placeholder="Handles customer questions and support requests"
            className="h-10"
          />
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-muted">Objective</label>
        <Textarea
          value={flow.agentObjective}
          onChange={(event) => flow.setAgentObjective(event.target.value)}
          aria-label="Objective"
          rows={4}
          placeholder="Resolve customer support requests accurately."
          className="min-h-28 resize-y"
        />
        <p className="mt-2 text-xs leading-5 text-muted">
          This objective initializes the Behavior. Configure the full Behavior in the Agent editor.
        </p>
      </div>
    </div>
  )
}
