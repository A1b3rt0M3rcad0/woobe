import { ServerCog } from 'lucide-react'

import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentContextAssemblerField } from './AgentContextAssemblerField'
import { AgentSessionModeField } from './AgentSessionModeField'

export function AgentRuntimeSettings({ projectId }: { projectId: string }) {
  const { state } = useAgentEditor()
  const sessionLabel = state.sessionMode === 'stateless' ? 'Stateless' : 'Stateful'

  return (
    <div className="p-3">
      <section aria-label="Runtime" className="rounded-container border border-border bg-surface/[0.72]">
        <div className="flex items-start gap-2.5 border-b border-border p-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><ServerCog className="h-3.5 w-3.5" /></span>
          <div className="min-w-0 flex-1"><p className="font-mono text-[9px] font-bold text-slate-50">Runtime</p><p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">Context Manager · {sessionLabel}</p></div>
        </div>

        <div className="space-y-4 p-3">
          <p className="font-sans text-[9px] leading-4 text-muted-foreground">Configure how this Agent assembles context and whether Session continuity is preserved between Runs.</p>
          <div className="rounded-container border border-border bg-background/20 p-3"><AgentContextAssemblerField projectId={projectId} compact /></div>
          <div className="rounded-container border border-border bg-background/20 p-3"><AgentSessionModeField compact /></div>
        </div>
      </section>
    </div>
  )
}
