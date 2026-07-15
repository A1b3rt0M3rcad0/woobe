import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { cancelNetworkExecution, resetNetworkSessionContext } from '@/features/network/api'
import { streamNetworkExecution } from '@/features/network/stream'
import type { NetworkRuntimeEvent } from '@/features/network/types'
import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import { buildTurnFromRuntimeEvents, type NetworkExecution, type NetworkTurn, type RuntimeEventRecord } from './networkChatExecution'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkChatComposer } from './NetworkChatComposer'
import { NetworkChatHeader } from './NetworkChatHeader'
import { NetworkChatHistory } from './NetworkChatHistory'

interface NetworkChatWorkspaceProps {
  networkId: string
  projectId: string
  networkName: string
  environment: Environment
  versionLabel: string
  currentVersionId: string | null
  bindings: Record<AgentNodeId, NetworkBinding>
  sessions: NetworkSession[]
  activeSession: NetworkSession
  historyTurns: NetworkTurn[]
  historyLoading: boolean
  onBeforeDraftRun: () => Promise<number>
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
  onRun: (trace: NetworkTraceRecord) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

function activityLabel(eventType: string, event: NetworkRuntimeEvent) {
  if (eventType === 'execution_accepted') return `Execution accepted in ${String(event.data.environment ?? 'runtime')}`
  if (eventType === 'execution_started') return 'Network worker started the execution'
  if (eventType === 'agent_invocation_started') return `Agent started: ${String(event.data.label ?? event.agent_id ?? 'unknown')}`
  if (eventType === 'agent_invocation_completed') return `Agent completed at depth ${event.depth ?? 0}`
  if (eventType === 'agent_invocation_failed') return `Agent failed: ${String(event.data.message ?? event.data.code ?? 'runtime error')}`
  if (eventType === 'delegation_started') return `Delegating to ${String(event.data.target ?? event.data.target_node_id ?? 'Agent')}`
  if (eventType === 'delegation_completed') return `Delegation completed: ${String(event.data.target ?? 'Agent')}`
  if (eventType === 'execution_completed') return 'Network execution completed'
  if (eventType === 'execution_failed') return `Execution failed: ${String(event.data.message ?? event.data.code ?? 'runtime error')}`
  if (eventType === 'execution_cancelled') return 'Network execution cancelled'
  return eventType.replace(/_/g, ' ')
}

export function NetworkChatWorkspace({
  networkId,
  projectId,
  networkName,
  environment,
  versionLabel,
  currentVersionId,
  bindings,
  sessions,
  activeSession,
  historyTurns,
  historyLoading,
  onBeforeDraftRun,
  onSelectSession,
  onNewSession,
  onRun,
  onSelectAgent,
  onOpenTrace,
}: NetworkChatWorkspaceProps) {
  const [text, setText] = useState('')
  const [turns, setTurns] = useState<NetworkTurn[]>(historyTurns)
  const [running, setRunning] = useState(false)
  const [liveAnswer, setLiveAnswer] = useState('')
  const [liveActivity, setLiveActivity] = useState<string[]>([])
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const executionIdRef = useRef<string | null>(null)
  const changed = environment !== 'draft' && activeSession.networkVersion !== currentVersionId
  const counts = Object.values(bindings).reduce<Record<NetworkBinding['source'], number>>(
    (result, binding) => ({ ...result, [binding.source]: result[binding.source] + 1 }),
    { draft: 0, staging: 0, release: 0 },
  )

  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => { setTurns(historyTurns) }, [historyTurns])
  useEffect(() => {
    const element = scrollRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [turns, running])

  const stop = () => {
    const wasRunning = running
    const executionId = executionIdRef.current
    abortRef.current?.abort()
    abortRef.current = null
    executionIdRef.current = null
    setRunning(false)
    setLiveAnswer('')
    setLiveActivity([])
    if (wasRunning && executionId) {
      void cancelNetworkExecution(executionId, projectId)
        .then(() => toast.info('Network execution cancellation requested'))
        .catch(() => toast.warning('Connection closed, but cancellation could not be confirmed'))
    } else if (wasRunning) {
      toast.info('Network execution connection stopped')
    }
  }

  const startNew = () => {
    if (running) return
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    setLiveAnswer('')
    setLiveActivity([])
    setTurns([])
    setText('')
    onNewSession()
  }

  const resetContext = async () => {
    if (running) return
    try {
      await resetNetworkSessionContext(networkId, activeSession.id, projectId)
      toast.success('Agent contexts reset for this Network Session')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to reset Network context')
    }
  }

  const send = async (suggestion?: string) => {
    const content = (suggestion ?? text).trim()
    if (!content || running) return
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
    const records: RuntimeEventRecord[] = []
    let answer = ''
    let executionId = ''
    let traceId = ''
    let status: NetworkExecution['status'] = 'success'

    try {
      const expectedDraftRevision = environment === 'draft' ? await onBeforeDraftRun() : undefined
      const executionBindings = environment === 'draft'
        ? Object.fromEntries(Object.entries(bindings).map(([nodeId, binding]) => [nodeId, { ...binding, version: `r${expectedDraftRevision}`, dirty: false }])) as Record<AgentNodeId, NetworkBinding>
        : bindings
      await streamNetworkExecution({
        networkId,
        projectId,
        networkSessionId: activeSession.id,
        message: content,
        expectedDraftRevision,
      }, {
        onExecutionId: (id) => {
          executionId = id
          executionIdRef.current = id
        },
        onEvent: (eventType, event) => {
          records.push({ eventType, event })
          if (eventType !== 'token') setLiveActivity((items) => [...items.slice(-5), activityLabel(eventType, event)])
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
          if (eventType === 'execution_failed' || eventType === 'execution_cancelled') status = 'error'
        },
        onHeartbeat: () => setLastHeartbeatAt(Date.now()),
      }, controller.signal)

      const turn = buildTurnFromRuntimeEvents({
        records,
        environment,
        bindings: executionBindings,
        executionId: executionId || crypto.randomUUID(),
        user: content,
        answer,
        fallbackTraceId: traceId,
        terminalStatus: status,
      })
      setTurns((items) => [...items, turn])
      onRun(createNetworkTraceRecord({
        execution: turn.execution,
        environment,
        bindings: executionBindings,
        networkSessionId: activeSession.id,
        title: content,
        userMessage: content,
        answer: turn.answer,
        usage: turn.usage,
        agentContexts: activeSession.agentContexts,
        parsedOutput: turn.parsedOutput,
        source: 'chat',
        runtimeEvents: records,
        networkVersion: environment === 'draft' ? `Draft r${expectedDraftRevision}` : versionLabel,
      }))
    } catch (error) {
      if (!controller.signal.aborted) {
        if (!executionId) setText(content)
        toast.error(error instanceof Error ? error.message : 'Network execution failed')
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      if (executionIdRef.current === executionId) executionIdRef.current = null
      setRunning(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <NetworkChatHeader environment={environment} versionLabel={versionLabel} counts={counts} sessions={sessions} activeSessionId={activeSession.id} changed={changed} newSessionDisabled={running} onSelectSession={onSelectSession} onNew={startNew} onResetContext={() => void resetContext()} />
      {historyLoading ? <div className="border-b border-border/60 px-4 py-2 text-[9px] text-muted">Loading persisted Network history…</div> : null}
      <NetworkChatHistory scrollRef={scrollRef} networkName={networkName} turns={turns} running={running} onSuggestion={send} onSelectAgent={onSelectAgent} onOpenTrace={onOpenTrace} />
      {running ? <div className="mx-4 mb-2 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-[10px]"><div className="flex items-center gap-2 text-primary-light"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />Live Network activity<span className="ml-auto text-[9px] text-muted">{lastHeartbeatAt ? 'heartbeat received' : 'connection open'}</span></div>{liveActivity.length ? <div className="mt-2 space-y-1 text-muted">{liveActivity.map((item, index) => <p key={`${index}-${item}`}>{item}</p>)}</div> : null}{liveAnswer ? <p className="mt-2 whitespace-pre-wrap border-t border-border/60 pt-2 text-slate-200">{liveAnswer}</p> : null}</div> : null}
      <NetworkChatComposer value={text} running={running} onChange={setText} onSend={() => send()} onStop={stop} />
    </div>
  )
}
