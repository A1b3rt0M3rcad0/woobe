import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'
import { providerLabel } from '@/features/agents/hooks/useAgentCreationFlow'

interface AgentReviewStepProps {
  flow: AgentCreationFlowController
}

export function AgentReviewStep({ flow }: AgentReviewStepProps) {
  const model = flow.selectedModel
  if (!model) return null

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="rounded-xl border border-border/80 bg-background/45 p-5">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Agent</p>
        <h3 className="mt-2 text-base font-semibold text-white">{flow.agentName.trim()}</h3>
        <p className="mt-2 text-sm leading-6 text-muted">
          {flow.agentDescription.trim() || 'No description provided.'}
        </p>
      </section>

      <section className="rounded-xl border border-border/80 bg-background/45 p-5">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Model binding</p>
        <h3 className="mt-2 truncate text-base font-semibold text-white" title={model.name}>{model.name}</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="text-xs text-muted">Provider</p>
            <p className="mt-1 text-sm text-white/90">{providerLabel(model.provider)}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Model ID</p>
            <p className="mt-1 truncate font-mono text-xs text-white/80" title={model.model}>{model.model}</p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-background/45 p-5 lg:col-span-2">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Instructions</p>
        <p className="mt-3 max-h-44 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-white/90">
          {flow.agentInstructions.trim()}
        </p>
      </section>
    </div>
  )
}
