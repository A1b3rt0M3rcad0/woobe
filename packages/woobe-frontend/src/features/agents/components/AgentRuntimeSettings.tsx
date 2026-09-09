import { AgentRuntimeSurface } from './AgentRuntimeSurface'

export function AgentRuntimeSettings({ projectId }: { projectId: string }) {
  return <div className="p-4"><AgentRuntimeSurface projectId={projectId} /></div>
}
