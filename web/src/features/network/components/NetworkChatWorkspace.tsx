import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import { currentSignature, makeExecution, type NetworkExecution, type NetworkTurn } from './networkChatExecution'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import { hashComposition, type NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkChatComposer } from './NetworkChatComposer'
import { NetworkChatHeader } from './NetworkChatHeader'
import { NetworkChatHistory } from './NetworkChatHistory'

interface NetworkChatWorkspaceProps {
  networkName: string
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  sessions: NetworkSession[]
  activeSession: NetworkSession
  pinned: boolean
  onSelectSession: (sessionId: string) => void
  onNewSession: (signature: string) => void
  onPin: () => void
  onRun: (trace: NetworkTraceRecord) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

function seedMessage(session: NetworkSession) {
  const title = session.title.toLowerCase()
  if (title.includes('invoice') || title.includes('refund')) return 'I need help with an invoice that was charged twice.'
  if (title.includes('password')) return 'I need help resetting a password after repeated login errors.'
  if (title.includes('timeout') || title.includes('incident')) return 'The public API is returning a 504 timeout.'
  return 'Review how this request should be routed through the Network.'
}

export function NetworkChatWorkspace({
  networkName,
  environment,
  bindings,
  sessions,
  activeSession,
  pinned,
  onSelectSession,
  onNewSession,
  onPin,
  onRun,
  onSelectAgent,
  onOpenTrace,
}: NetworkChatWorkspaceProps) {
  const seed = useMemo(() => makeExecution(seedMessage(activeSession), environment, bindings, activeSession.id, activeSession.agentContexts), [activeSession.id])
  const [text, setText] = useState('')
  const [turns, setTurns] = useState<NetworkTurn[]>(activeSession.messageCount > 0 ? [{ id: `seed-${activeSession.id}`, user: seedMessage(activeSession), answer: seed.answer, parsedOutput: seed.parsedOutput, provider: seed.provider, model: seed.model, usage: seed.usage, execution: seed.execution }] : [])
  const [running, setRunning] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const signature = currentSignature(environment, bindings)
  const changed = hashComposition(signature) !== activeSession.compositionHash
  const counts = Object.values(bindings).reduce<Record<NetworkBinding['source'], number>>((result, binding) => ({ ...result, [binding.source]: result[binding.source] + 1 }), { draft: 0, staging: 0, release: 0 })

  useEffect(() => () => { if (timeoutRef.current) clearTimeout(timeoutRef.current) }, [])
  useEffect(() => { const element = scrollRef.current; if (element) element.scrollTop = element.scrollHeight }, [turns, running])

  const stop = () => {
    const wasRunning = running || Boolean(timeoutRef.current)
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = null
    setRunning(false)
    if (wasRunning) toast.info('Network execution stopped')
  }

  const startNew = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = null
    setRunning(false)
    setTurns([])
    setText('')
    onNewSession(signature)
  }

  const send = (suggestion?: string) => {
    const content = (suggestion ?? text).trim()
    if (!content || running) return
    if (changed && !pinned) { toast.warning('Start a new session or continue with the pinned composition before sending'); return }
    setText('')
    setRunning(true)
    timeoutRef.current = setTimeout(() => {
      const result = makeExecution(content, environment, bindings, activeSession.id, activeSession.agentContexts)
      setTurns((items) => [...items, { id: result.execution.id, user: content, answer: result.answer, parsedOutput: result.parsedOutput, provider: result.provider, model: result.model, usage: result.usage, execution: result.execution }])
      setRunning(false)
      timeoutRef.current = null
      onRun(createNetworkTraceRecord({
        execution: result.execution,
        environment,
        bindings,
        networkSessionId: activeSession.id,
        title: content,
        userMessage: content,
        answer: result.answer,
        usage: result.usage,
        agentContexts: result.agentContexts,
        parsedOutput: result.parsedOutput,
        source: 'chat',
      }))
    }, 520)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <NetworkChatHeader
        environment={environment}
        counts={counts}
        sessions={sessions}
        activeSessionId={activeSession.id}
        changed={changed}
        pinned={pinned}
        onSelectSession={onSelectSession}
        onNew={startNew}
        onPin={onPin}
      />
      <NetworkChatHistory scrollRef={scrollRef} networkName={networkName} turns={turns} running={running} onSuggestion={send} onSelectAgent={onSelectAgent} onOpenTrace={onOpenTrace} />
      <NetworkChatComposer value={text} running={running} onChange={setText} onSend={() => send()} onStop={stop} />
    </div>
  )
}
