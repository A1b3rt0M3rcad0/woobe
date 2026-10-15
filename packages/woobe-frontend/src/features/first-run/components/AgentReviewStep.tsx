import { Button, SectionBlock } from '@woobe/ui'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'
import { providerLabel } from '@/features/agents/hooks/useAgentCreationFlow'

interface AgentReviewStepProps { flow: AgentCreationFlowController }
export function AgentReviewStep({ flow }: AgentReviewStepProps) {
  const model = flow.selectedModel
  if (!model) return null
  const credential = flow.credentials.find(item => item.id === model.provider_credential_id)
  return <div className="space-y-5">
    <SectionBlock title="Agent instructions" actions={<Button size="sm" variant="ghost" onClick={() => flow.setStep('details')}>Edit instructions</Button>}>
      <p className="break-words text-base font-medium text-foreground">{flow.agentName.trim()}</p>
      {flow.agentDescription.trim() && <p className="mt-1 text-sm text-muted-foreground">{flow.agentDescription.trim()}</p>}
      <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">{flow.agentObjective.trim()}</p>
    </SectionBlock>
    <SectionBlock title="Model" actions={<Button size="sm" variant="ghost" onClick={() => flow.setStep('model')}>Change model</Button>}>
      <dl className="grid gap-4 text-sm sm:grid-cols-2">
        <div><dt className="text-muted-foreground">Name</dt><dd className="mt-1 break-words text-foreground">{model.name}</dd></div>
        <div><dt className="text-muted-foreground">Provider connection</dt><dd className="mt-1 break-words text-foreground">{credential?.name || providerLabel(model.provider)}</dd></div>
        <div className="sm:col-span-2"><dt className="text-muted-foreground">Model ID</dt><dd className="mt-1 break-all font-mono text-xs text-foreground">{model.model}</dd></div>
      </dl>
    </SectionBlock>
    <div className="border-l-2 border-primary pl-4 text-sm leading-6">
      <p className="font-medium text-foreground">Next: test your Draft in the Playground</p>
      <p className="mt-1 text-muted-foreground">No test message is sent during setup. Sending a message in the Playground uses your provider and may incur charges. Staging and Production are configured separately.</p>
    </div>
  </div>
}
