import { ServerCog } from 'lucide-react'
import { PanelHeader } from '@woobe/ui'

import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentContextAssemblerField } from './AgentContextAssemblerField'
import { AgentSessionModeField } from './AgentSessionModeField'

export function AgentRuntimeSettings({ projectId }: { projectId: string }) {
  const { state } = useAgentEditor()
  const sessionLabel = state.sessionMode === 'stateless' ? 'Stateless' : 'Stateful'

  return (
    <div className="p-ui-md">
      <section aria-label="Runtime" className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader icon={<ServerCog className="h-3.5 w-3.5" />} title="Runtime" description={`Context Manager · ${sessionLabel}`} />

        <div className="space-y-ui-lg p-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">Configure how this Agent assembles context and whether Session continuity is preserved between Runs.</p>
          <div className="rounded-container border border-border bg-background/20 p-ui-md"><AgentContextAssemblerField projectId={projectId} compact /></div>
          <div className="rounded-container border border-border bg-background/20 p-ui-md"><AgentSessionModeField compact /></div>
        </div>
      </section>
    </div>
  )
}
