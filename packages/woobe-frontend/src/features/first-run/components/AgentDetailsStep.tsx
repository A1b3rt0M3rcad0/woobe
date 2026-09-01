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
        <label className="mb-1.5 block text-sm font-medium text-muted">Instructions</label>
        <Textarea
          value={flow.agentInstructions}
          onChange={(event) => flow.setAgentInstructions(event.target.value)}
          rows={10}
          placeholder="You are a customer support Agent. Answer clearly, use the available knowledge and do not invent information."
          className="min-h-56 resize-none"
        />
        <p className="mt-2 text-xs leading-5 text-muted">
          These instructions initialize the Agent Draft and remain editable in the Playground.
        </p>
      </div>
    </div>
  )
}
