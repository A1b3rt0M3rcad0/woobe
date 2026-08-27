import { memo, type Ref, type UIEventHandler } from 'react'
import { Workflow } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { useNetworkIdentity } from '@/features/network/NetworkIdentityContext'
import { ChatMessage } from '@/features/playground/components/ChatMessage'
import type { ChatMessage as PlaygroundChatMessage } from '@/features/playground/types'

import type { LiveNetworkExecutionState } from './networkLiveExecution'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkExecution, NetworkTurn } from './networkChatExecution'
import { NetworkAnswer, NetworkLiveAgents } from './NetworkExecutionTree'

interface NetworkChatHistoryProps {
  scrollRef: Ref<HTMLDivElement>
  networkName: string
  turns: NetworkTurn[]
  running: boolean
  pendingMessage: string | null
  liveAnswer: string
  liveActivity: string[]
  liveExecution: LiveNetworkExecutionState
  liveResponseCommitted: boolean
  liveParsedOutput: Record<string, unknown> | null
  liveOutputParseError: string | null
  onScroll?: UIEventHandler<HTMLDivElement>
  onSuggestion: (value: string) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

interface PersistedNetworkTurnsProps {
  networkName: string
  turns: NetworkTurn[]
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

const onboardingSuggestions = [
  'Test a request that should be answered by the entry Agent.',
  'Test a request that should require delegation to a specialist.',
]

const PersistedNetworkTurns = memo(function PersistedNetworkTurns({
  networkName,
  turns,
  onSelectAgent,
  onOpenTrace,
}: PersistedNetworkTurnsProps) {
  return turns.map((turn) => (
    <div key={turn.id} className="space-y-4">
      <ChatMessage message={{ role: 'user', content: turn.user }} variant="network" />
      <NetworkAnswer
        networkName={networkName}
        turn={turn}
        onOpenTrace={onOpenTrace}
        onSelectAgent={onSelectAgent}
      />
    </div>
  ))
})

export function NetworkChatHistory({
  scrollRef,
  networkName,
  turns,
  running,
  pendingMessage,
  liveAnswer,
  liveActivity,
  liveExecution,
  liveResponseCommitted,
  liveParsedOutput,
  liveOutputParseError,
  onScroll,
  onSuggestion,
  onSelectAgent,
  onOpenTrace,
}: NetworkChatHistoryProps) {
  const exactNetworkName = useNetworkIdentity() ?? networkName
  const liveMessage: PlaygroundChatMessage = {
    role: 'assistant',
    content: liveAnswer,
    parsed_output: liveParsedOutput,
    output_parse_error: liveOutputParseError,
    activity: {
      status: liveAnswer ? 'generating_answer' : 'working',
      message: liveActivity[liveActivity.length - 1] ?? 'Executing Network composition…',
    },
    tool_calls: liveExecution.tools,
    sources: liveExecution.sources,
  }

  return (
    <ScrollArea ref={scrollRef} className="min-h-0 flex-1 overscroll-contain" onScroll={onScroll}>
      <div className="mx-auto max-w-4xl space-y-6 px-5 py-5">
        {turns.length === 0 && !running ? (
          <div className="flex min-h-[360px] flex-col items-center justify-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/25 bg-primary/10"><Workflow className="h-5 w-5 text-primary-light" /></div>
            <h2 className="mt-4 text-sm font-semibold text-white">Test the complete Network</h2>
            <p className="mt-1 max-w-md text-[10px] leading-5 text-muted">Every message starts at the entry Agent and executes the saved composition.</p>
            <div className="mt-4 grid w-full max-w-lg gap-2 sm:grid-cols-2">{onboardingSuggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => onSuggestion(suggestion)} className="rounded-xl border border-border bg-surface/45 px-3 py-2.5 text-left text-[10px] text-muted hover:border-primary/30 hover:text-white">{suggestion}</button>)}</div>
          </div>
        ) : null}

        <PersistedNetworkTurns
          networkName={exactNetworkName}
          turns={turns}
          onSelectAgent={onSelectAgent}
          onOpenTrace={onOpenTrace}
        />

        {running && pendingMessage ? (
          <div className="space-y-4">
            <ChatMessage message={{ role: 'user', content: pendingMessage }} variant="network" />
            <ChatMessage
              message={liveMessage}
              agentName={exactNetworkName}
              variant="network"
              assistantIcon="network"
              details={<NetworkLiveAgents agents={liveExecution.agents} onSelectAgent={onSelectAgent} />}
              isStreaming={!liveResponseCommitted}
            />
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
