import { SectionBlock } from '@woobe/ui'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'
import { providerLabel } from '@/features/agents/hooks/useAgentCreationFlow'

interface AgentReviewStepProps { flow: AgentCreationFlowController }

export function AgentReviewStep({ flow }: AgentReviewStepProps) {
  const model = flow.selectedModel
  if (!model) return null

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <SectionBlock title="Agent" density="compact">
        <p className="font-mono text-[11px] font-semibold text-slate-100">{flow.agentName.trim()}</p>
        <p className="mt-1 font-sans text-xs leading-5 text-muted">{flow.agentDescription.trim() || 'No description provided.'}</p>
      </SectionBlock>
      <SectionBlock title="Model binding" density="compact">
        <p className="truncate font-mono text-[11px] font-semibold text-slate-100" title={model.name}>{model.name}</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-2"><div><p className="font-mono text-[9px] text-muted">Provider</p><p className="mt-0.5 text-xs text-slate-200">{providerLabel(model.provider)}</p></div><div><p className="font-mono text-[9px] text-muted">Model ID</p><p className="mt-0.5 truncate font-mono text-[10px] text-slate-200" title={model.model}>{model.model}</p></div></div>
      </SectionBlock>
      <SectionBlock title="Objective" density="compact" className="lg:col-span-2">
        <p className="max-h-40 overflow-y-auto whitespace-pre-wrap font-sans text-xs leading-5 text-slate-200">{flow.agentObjective.trim()}</p>
      </SectionBlock>
    </div>
  )
}
