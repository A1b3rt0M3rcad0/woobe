import { ServerCog } from 'lucide-react'
import { PanelHeader } from '@woobe/ui'

import {
  executionStrategyDescriptor,
  executionStrategyFromRuntimeConfig,
} from '@/features/agents/executionStrategy'
import { useExecutionStrategies } from '@/features/agents/hooks'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentContextAssemblerField } from './AgentContextAssemblerField'
import { AgentExecutionStrategyField } from './AgentExecutionStrategyField'
import { AgentIntermediateMessagesField } from './AgentIntermediateMessagesField'
import { AgentSessionModeField } from './AgentSessionModeField'

export function AgentRuntimeSettings({ projectId }: { projectId: string }) {
  const { state } = useAgentEditor()
  const { data: strategies = [] } = useExecutionStrategies()
  const sessionLabel = state.sessionMode === 'stateless' ? 'Stateless' : 'Stateful'
  const selectedStrategy = executionStrategyFromRuntimeConfig(state.runtimeConfig)
  const strategyLabel = executionStrategyDescriptor(strategies, selectedStrategy)?.display_name ?? selectedStrategy

  return (
    <div className="p-ui-md">
      <section aria-label="Runtime" className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader icon={<ServerCog className="h-3.5 w-3.5" />} title="Runtime" description={`${strategyLabel} execution · Context Manager · ${sessionLabel}`} />

        <div className="space-y-ui-lg p-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">Configure how this Agent conducts execution, assembles context, and preserves Session continuity between Runs.</p>
          <div className="rounded-container border border-border bg-background/20 p-ui-md"><AgentExecutionStrategyField compact /></div>
          <div className="rounded-container border border-border bg-background/20 p-ui-md"><AgentIntermediateMessagesField compact /></div>
          <div className="rounded-container border border-border bg-background/20 p-ui-md"><AgentContextAssemblerField projectId={projectId} compact /></div>
          <div className="rounded-container border border-border bg-background/20 p-ui-md"><AgentSessionModeField compact /></div>
        </div>
      </section>
    </div>
  )
}
