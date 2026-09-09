import { ServerCog } from 'lucide-react'

import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentContextAssemblerField } from './AgentContextAssemblerField'
import { AgentSessionModeField } from './AgentSessionModeField'

export function AgentRuntimeSettings({ projectId }: { projectId: string }) {
  const { state } = useAgentEditor()
  const sessionLabel = state.sessionMode === 'stateless' ? 'Stateless' : 'Stateful'

  return (
    <div className="p-4">
      <section aria-label="Runtime" className="rounded-xl border border-border bg-surface">
        <div className="flex items-center gap-3 p-4">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light">
            <ServerCog className="h-4 w-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold text-foreground">Runtime</span>
            <span className="mt-0.5 block text-[11px] text-muted">Context Manager · {sessionLabel}</span>
          </span>
        </div>

        <div className="space-y-5 border-t border-border p-4">
          <p className="text-xs leading-5 text-muted">
            Controls how this Agent builds context and maintains continuity between Runs.
          </p>

          <AgentContextAssemblerField projectId={projectId} compact />

          <div className="border-t border-border/80 pt-5">
            <AgentSessionModeField compact />
          </div>
        </div>
      </section>
    </div>
  )
}
