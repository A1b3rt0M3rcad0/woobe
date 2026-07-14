import type { Ref } from 'react'
import { Loader2, Workflow } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'

import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkExecution, NetworkTurn } from './networkChatExecution'
import { NetworkAnswer } from './NetworkExecutionTree'

interface NetworkChatHistoryProps {
  scrollRef: Ref<HTMLDivElement>
  networkName: string
  turns: NetworkTurn[]
  running: boolean
  onSuggestion: (value: string) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

export function NetworkChatHistory({ scrollRef, networkName, turns, running, onSuggestion, onSelectAgent, onOpenTrace }: NetworkChatHistoryProps) {
  return (
    <ScrollArea ref={scrollRef} className="min-h-0 flex-1 overscroll-contain">
      <div className="mx-auto max-w-4xl space-y-6 px-5 py-5">
        {turns.length === 0 && !running ? (
          <div className="flex min-h-[360px] flex-col items-center justify-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/25 bg-primary/10">
              <Workflow className="h-5 w-5 text-primary-light" />
            </div>
            <h2 className="mt-4 text-sm font-semibold text-white">Test the complete Network</h2>
            <p className="mt-1 max-w-md text-[10px] leading-5 text-muted">Every message enters through ENTRY and executes the selected composition.</p>
            <div className="mt-4 grid w-full max-w-lg gap-2 sm:grid-cols-2">
              {['Investigate a duplicate invoice charge.', 'Diagnose an API timeout incident.'].map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => onSuggestion(suggestion)} className="rounded-xl border border-border bg-surface/45 px-3 py-2.5 text-left text-[10px] text-muted hover:border-primary/30 hover:text-white">
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {turns.map((turn) => (
          <div key={turn.id} className="space-y-4">
            <div className="flex justify-end">
              <div className="max-w-[78%] rounded-xl rounded-br-md bg-primary px-4 py-3 text-[12px] leading-5 text-white shadow-sm shadow-black/10">{turn.user}</div>
            </div>
            <NetworkAnswer networkName={networkName} turn={turn} onOpenTrace={onOpenTrace} onSelectAgent={onSelectAgent} />
          </div>
        ))}

        {running ? (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10"><Workflow className="h-4 w-4 text-primary-light" /></div>
            <div className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-3 text-[10px] text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />Executing Network composition…</div>
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
