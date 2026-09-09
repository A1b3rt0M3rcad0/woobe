import { AgentContextAssemblerField } from './AgentContextAssemblerField'
import { AgentSessionModeField } from './AgentSessionModeField'

export function AgentRuntimeSettings({ projectId }: { projectId: string }) {
  return <div className="space-y-4 p-4">
    <AgentContextAssemblerField projectId={projectId} />
    <AgentSessionModeField />
  </div>
}
