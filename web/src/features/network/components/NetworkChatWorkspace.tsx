import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import { streamNetworkExecution } from '@/features/network/stream'
import { currentSignature, makeExecution, type NetworkExecution, type NetworkTurn } from './networkChatExecution'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import { hashComposition, type NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import type { NetworkRuntimeEvent } from '@/features/network/types'
import { NetworkChatComposer } from './NetworkChatComposer'
import { NetworkChatHeader } from './NetworkChatHeader'
import { NetworkChatHistory } from './NetworkChatHistory'

interface NetworkChatWorkspaceProps {
  networkId: string
  projectId: string
  networkName: string
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  sessions: NetworkSession[]
  activeSession: NetworkSession
  pinned: boolean
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
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

function activityLabel(eventType: string, event: NetworkRuntimeEvent) {
  if (eventType === 'execution_accepted') return 'Execution accepted and queued'
  if (eventType === 'execution_started') return 'Network worker started the execution'
  if (eventType === 'agent_invocation_started') return `Agent started: ${String(event.data.label ?? event.agent_id ?? 'unknown')}`
  if (eventType === 'agent_invocation_completed') return `Agent completed at depth ${event.depth ?? 0}`
  if (eventType === 'delegation_started') return `Delegating to ${String(event.data.target ?? event.data.target_node_id ?? 'Agent')}`
  if (eventType === 'delegation_completed') return `Delegation completed: ${String(event.data.target ?? 'Agent')}`
  if (eventType === 'execution_completed') return 'Network execution completed'
  if (eventType === 'execution_failed') return `Execution failed: ${String(event.data.message ?? event.data.code ?? 'runtime error')}`
  if (eventType === 'execution_cancelled') return 'Network execution cancelled'
  return eventType.replaceAll('_', ' ')
}

export function NetworkChatWorkspace({
  networkId,
  projectId,
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
  const [liveAnswer, setLiveAnswer] = useState('')
  const [liveActivity, setLiveActivity] = useState<string[]>([])
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const signature = currentSignature(environment, bindings)
  const changed = hashComposition(signature) !== activeSession.compositionHash
  const counts = Object.values(bindings).reduce<Record<NetworkBinding['source'], number>>((result, binding) => ({ ...result, [binding.source]: result[binding.source] + 1 }), { draft: 0, staging: 0, release: 0 })

  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => { const element = scrollRef.current; if (element) element.scrollTop = element.scrollHeight }, [turns, running])

  const stop = () => {
    const wasRunning = running
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    setLiveAnswer('')
    setLiveActivity([])
    if (wasRunning) toast.info('Network execution connection stopped; server execution may continue')
  }

  const startNew = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    setLiveAnswer('')
    setLiveActivity([])
    setTurns([])
    setText('')
    onNewSession()
  }

  const send = async (suggestion?: string) => {
    const content = (suggestion ?? text).trim()
    if (!content || running) return
    if (environment === 'draft') {
      toast.info('Stage the Network before running it')
      return
    }
    if (changed) {
      toast.warning(`Start a new ${environment} session for the current Network version before sending`)
      return
    }
    setText('')
    setRunning(true)
    setLiveAnswer('')
    setLiveActivity([])
    setLastHeartbeatAt(null)
    const controller = new AbortController()
    abortRef.current = controller
    let answer = ''
    let executionId = ''
    let traceId = ''
    try {
      await streamNetworkExecution({
        networkId,
        projectId,
        networkSessionId: activeSession.id,
        message: content,
      }, {
        onExecutionId: (id) => { executionId = id },
        onEvent: (eventType, event) => {
          if (eventType !== 'token') {
            setLiveActivity((items) => [...items.slice(-5), activityLabel(eventType, event)])
          }
          if (eventType === 'token') {
            const chunk = event.data.content
            if (typeof chunk === 'string') {
              answer += chunk
              setLiveAnswer(answer)
            }
          }
          if (eventType === 'execution_completed') {
            const id = event.data.trace_id
            if (typeof id === 'string') traceId = id
          }
        },
        onHeartbeat: () => setLastHeartbeatAt(Date.now()),
      }, controller.signal)

      const result = makeExecution(content, environment, bindings, activeSession.id, activeSession.agentContexts)
      result.answer = answer || result.answer
      if (executionId) result.execution.id = executionId
      if (traceId) result.execution.traceId = traceId
      setTurns((items) => [...items, {
        id: result.execution.id,
        user: content,
        answer: result.answer,
        parsedOutput: result.parsedOutput,
        provider: result.provider,
        model: result.model,
        usage: result.usage,
        execution: result.execution,
      }])
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
    } catch (error) {
      if (!controller.signal.aborted) {
        toast.error(error instanceof Error ? error.message : 'Network execution failed')
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setRunning(false)
    }
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
      {running ? <div className="mx-4 mb-2 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-[10px]">
        <div className="flex items-center gap-2 text-primary-light"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />Live Network activity<span className="ml-auto text-[9px] text-muted">{lastHeartbeatAt ? 'heartbeat received' : 'connection open'}</span></div>
        {liveActivity.length ? <div className="mt-2 space-y-1 text-muted">{liveActivity.map((item, index) => <p key={`${index}-${item}`}>{item}</p>)}</div> : null}
        {liveAnswer ? <p className="mt-2 whitespace-pre-wrap border-t border-border/60 pt-2 text-slate-200">{liveAnswer}</p> : null}
      </div> : null}
      <NetworkChatComposer value={text} running={running} onChange={setText} onSend={() => send()} onStop={stop} />
    </div>
  )
}
