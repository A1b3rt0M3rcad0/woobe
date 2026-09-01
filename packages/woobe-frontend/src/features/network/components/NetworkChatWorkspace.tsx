import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { cancelNetworkExecution, resetNetworkSessionContext } from '@/features/network/api'
import { useNetworkRuntimeEnvironments } from '@/features/network/hooks'
import { getActiveNetworkExecution } from '@/features/network/runtime-reattach-api'
import { streamNetworkExecution } from '@/features/network/stream'
import type { NetworkRuntimeEvent } from '@/features/network/types'
import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import { buildTurnFromRuntimeEvents, type NetworkExecution, type NetworkTurn, type RuntimeEventRecord } from './networkChatExecution'
import { createNetworkLiveAnswerScheduler } from './networkLiveAnswerScheduler'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkChatComposer } from './NetworkChatComposer'
import { NetworkChatHeader } from './NetworkChatHeader'
import { NetworkChatHistory } from './NetworkChatHistory'
import { applyNetworkRuntimeEvent, emptyLiveNetworkExecution } from './networkLiveExecution'
import { reconcileNetworkTurns } from './networkTurnReconciliation'

interface NetworkChatWorkspaceProps {
  networkId: string
  projectId: string
  networkName: string
  environment: Environment
  versionLabel: string
  currentVersionId: string | null
  bindings: Record<AgentNodeId, NetworkBinding>
  sessions: NetworkSession[]
  activeSession: NetworkSession | null
  historyTurns: NetworkTurn[]
  historyLoading: boolean
  onBeforeDraftRun: () => Promise<number>
  onSelectSession: (sessionId: string) => void
  onCreateSession: () => Promise<NetworkSession | null>
  onStartNewConversation: () => void
  onRun: (trace: NetworkTraceRecord) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

const BOTTOM_THRESHOLD_PX = 56
const LIVE_EXECUTION_EVENT_TYPES = new Set([
  'agent_invocation_started',
  'agent_invocation_completed',
  'agent_invocation_failed',
  'agent_invocation_cancelled',
  'tool_call_started',
  'tool_call_completed',
  'sources',
  'delegation_started',
  'delegation_completed',
  'delegation_failed',
  'delegation_skipped',
  'execution_failed',
  'execution_cancelled',
])

function activityLabel(eventType: string, event: NetworkRuntimeEvent) {
  if (eventType === 'execution_accepted') return `Execution accepted in ${String(event.data.environment ?? 'runtime')}`
  if (eventType === 'execution_started') return 'Network worker started the execution'
  if (eventType === 'agent_activity') return String(event.data.message ?? event.data.status ?? 'Agent is working')
  if (eventType === 'agent_invocation_started') return `Agent started: ${String(event.data.label ?? event.agent_id ?? 'unknown')}`
  if (eventType === 'agent_invocation_completed') return `Agent completed at depth ${event.depth ?? 0}`
  if (eventType === 'agent_invocation_failed') return `Agent failed: ${String(event.data.message ?? event.data.code ?? 'runtime error')}`
  if (eventType === 'agent_invocation_cancelled') return `Agent cancelled at depth ${event.depth ?? 0}`
  if (eventType === 'tool_call_started') return `Calling tool: ${String(event.data.tool_name ?? 'tool')}`
  if (eventType === 'tool_call_completed') return `Tool completed: ${String(event.data.tool_name ?? 'tool')}`
  if (eventType === 'delegation_started') return `Delegating to ${String(event.data.target ?? event.data.target_node_id ?? 'Agent')}`
  if (eventType === 'delegation_completed') return `Delegation completed: ${String(event.data.target ?? 'Agent')}`
  if (eventType === 'delegation_failed') return `Delegation failed: ${String(event.data.target ?? 'Agent')}`
  if (eventType === 'delegation_skipped') return `Delegation skipped: ${String(event.data.target ?? 'Agent')}`
  if (eventType === 'execution_completed') return 'Network execution completed'
  if (eventType === 'execution_failed') return `Execution failed: ${String(event.data.message ?? event.data.code ?? 'runtime error')}`
  if (eventType === 'execution_cancelled') return 'Network execution cancelled'
  return eventType.replace(/_/g, ' ')
}

function isNearBottom(element: HTMLDivElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_THRESHOLD_PX
}

function isPublicFinalToken(event: NetworkRuntimeEvent) {
  return event.data.visibility === 'assistant' && event.data.channel === 'final'
}

function updatesLiveExecution(eventType: string) {
  return LIVE_EXECUTION_EVENT_TYPES.has(eventType)
}

function shouldRecordRuntimeEvent(eventType: string) {
  return eventType !== 'token' && eventType !== 'token_retract' && eventType !== 'run.state'
}

function parsedOutputFromEvent(event: NetworkRuntimeEvent): Record<string, unknown> | null {
  const value = event.data.parsed_output
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

export function NetworkChatWorkspace({ networkId, projectId, networkName, environment, versionLabel, currentVersionId, bindings, sessions, activeSession, historyTurns, historyLoading, onBeforeDraftRun, onSelectSession, onCreateSession, onStartNewConversation, onRun, onSelectAgent, onOpenTrace }: NetworkChatWorkspaceProps) {
  const queryClient = useQueryClient()
  const runtimeStatesQuery = useNetworkRuntimeEnvironments(networkId, projectId)
  const runtimeEnabled = runtimeStatesQuery.data?.[environment]?.enabled ?? true
  const [text, setText] = useState('')
  const [localTurns, setLocalTurns] = useState<NetworkTurn[]>([])
  const [creatingSession, setCreatingSession] = useState(false)
  const [running, setRunning] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [liveAnswer, setLiveAnswer] = useState('')
  const [liveActivity, setLiveActivity] = useState<string[]>([])
  const [liveExecution, setLiveExecution] = useState(emptyLiveNetworkExecution)
  const [liveResponseCommitted, setLiveResponseCommitted] = useState(false)
  const [liveParsedOutput, setLiveParsedOutput] = useState<Record<string, unknown> | null>(null)
  const [liveOutputParseError, setLiveOutputParseError] = useState<string | null>(null)
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const shouldStickToBottomRef = useRef(true)
  const abortRef = useRef<AbortController | null>(null)
  const executionIdRef = useRef<string | null>(null)
  const stopIntentRef = useRef(false)
  const stopRequestRef = useRef(false)
  const reattachExecutionRef = useRef<string | null>(null)
  const previousSessionIdRef = useRef<string | null>(activeSession?.id ?? null)
  const mountedRef = useRef(true)
  const liveAnswerSchedulerRef = useRef<ReturnType<typeof createNetworkLiveAnswerScheduler> | null>(null)
  if (liveAnswerSchedulerRef.current === null) {
    liveAnswerSchedulerRef.current = createNetworkLiveAnswerScheduler(setLiveAnswer)
  }
  const changed = Boolean(activeSession && environment !== 'draft' && activeSession.networkVersion !== currentVersionId)
  const turns = useMemo(() => reconcileNetworkTurns(historyTurns, localTurns), [historyTurns, localTurns])
  const counts = Object.values(bindings).reduce<Record<NetworkBinding['source'], number>>((result, binding) => ({ ...result, [binding.source]: result[binding.source] + 1 }), { draft: 0, staging: 0, release: 0 })

  const scheduleLiveAnswer = (answer: string) => {
    liveAnswerSchedulerRef.current?.schedule(answer)
  }

  const flushLiveAnswer = (answer: string) => {
    liveAnswerSchedulerRef.current?.flush(answer)
  }

  const clearLiveState = () => {
    liveAnswerSchedulerRef.current?.clear()
    stopIntentRef.current = false
    stopRequestRef.current = false
    setRunning(false)
    setStopping(false)
    setPendingMessage(null)
    setLiveAnswer('')
    setLiveActivity([])
    setLiveExecution(emptyLiveNetworkExecution())
    setLiveResponseCommitted(false)
    setLiveParsedOutput(null)
    setLiveOutputParseError(null)
  }

  useLayoutEffect(() => () => {
    mountedRef.current = false
    liveAnswerSchedulerRef.current?.clear()
    abortRef.current?.abort()
    abortRef.current = null
  }, [])
  useLayoutEffect(() => {
    const nextSessionId = activeSession?.id ?? null
    if (previousSessionIdRef.current === nextSessionId) return
    previousSessionIdRef.current = nextSessionId
    if (running || creatingSession) return
    abortRef.current?.abort()
    abortRef.current = null
    executionIdRef.current = null
    clearLiveState()
    setLocalTurns([])
    setText('')
  }, [activeSession?.id, creatingSession, running])
  useLayoutEffect(() => {
    const persistedIds = new Set(historyTurns.map((turn) => turn.id))
    if (persistedIds.size) setLocalTurns((current) => current.filter((turn) => !persistedIds.has(turn.id)))
  }, [historyTurns])
  useLayoutEffect(() => {
    const element = scrollRef.current
    if (element && shouldStickToBottomRef.current) element.scrollTop = element.scrollHeight
  }, [turns.length, running, liveAnswer, liveActivity.length, liveExecution.agents.length, liveExecution.delegations.length, liveExecution.tools.length, liveExecution.sources.length])

  const refreshPersistedSession = async (sessionId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['network-session-messages', projectId, networkId, sessionId] }),
      queryClient.invalidateQueries({ queryKey: ['network-sessions', projectId, networkId] }),
    ])
  }

  const requestCancellation = (executionId: string) => {
    stopIntentRef.current = false
    setStopping(true)
    setLiveActivity((items) => [...items.slice(-5), 'Cancellation requested. Waiting for runtime finalization...'])
    void cancelNetworkExecution(executionId, projectId)
      .then(() => toast.info('Network execution cancellation requested'))
      .catch((error) => {
        stopRequestRef.current = false
        setStopping(false)
        toast.warning(error instanceof Error ? error.message : 'Run cancellation could not be confirmed')
      })
  }

  useLayoutEffect(() => {
    if (!networkId || !projectId || !runtimeEnabled || running || creatingSession) return
    let disposed = false

    void (async () => {
      let active
      try {
        active = await getActiveNetworkExecution({
          networkSessionId: activeSession?.id,
          networkId,
          environment,
        })
      } catch {
        return
      }
      if (!active || disposed || reattachExecutionRef.current === active.execution_id) return

      if (!activeSession || activeSession.id !== active.network_session_id) {
        onSelectSession(active.network_session_id)
        return
      }

      reattachExecutionRef.current = active.execution_id
      executionIdRef.current = active.execution_id
      liveAnswerSchedulerRef.current?.clear()
      setRunning(true)
      stopRequestRef.current = active.status === 'cancel_requested'
      setStopping(active.status === 'cancel_requested')
      setPendingMessage(active.input_message)
      setLiveAnswer('')
      setLiveActivity([active.status === 'cancel_requested' ? 'Stopping active Network Run...' : 'Resuming active Network Run...'])
      setLiveExecution(emptyLiveNetworkExecution())
      setLiveResponseCommitted(false)
      setLiveParsedOutput(null)
      setLiveOutputParseError(null)
      setLastHeartbeatAt(null)
      shouldStickToBottomRef.current = true

      const controller = new AbortController()
      abortRef.current = controller
      let answer = ''
      let terminalObserved = false
      try {
        await streamNetworkExecution({
          networkId,
          projectId,
          networkSessionId: active.network_session_id,
          executionId: active.execution_id,
          message: active.input_message,
        }, {
          onExecutionId: (id) => { executionIdRef.current = id },
          onEvent: (eventType, event) => {
            if (updatesLiveExecution(eventType)) {
              setLiveExecution((current) => applyNetworkRuntimeEvent(current, eventType, event))
            }
            if (eventType !== 'token' && eventType !== 'token_retract' && eventType !== 'run.state') {
              setLiveActivity((items) => [...items.slice(-5), activityLabel(eventType, event)])
            }
            if (eventType === 'token' && isPublicFinalToken(event)) {
              const chunk = event.data.content
              if (typeof chunk === 'string') {
                answer += chunk
                scheduleLiveAnswer(answer)
              }
            }
            if (eventType === 'token_retract') {
              const length = event.data.content_length
              if (typeof length === 'number' && length > 0) {
                answer = answer.slice(0, Math.max(0, answer.length - length))
                scheduleLiveAnswer(answer)
              }
            }
            if (eventType === 'agent_invocation_completed' && !event.parent_invocation_id) {
              flushLiveAnswer(answer)
              setLiveParsedOutput(parsedOutputFromEvent(event))
              setLiveOutputParseError(typeof event.data.output_parse_error === 'string' ? event.data.output_parse_error : null)
              setLiveResponseCommitted(true)
            }
            if (eventType === 'execution_completed') {
              flushLiveAnswer(answer)
              setLiveParsedOutput(parsedOutputFromEvent(event))
              setLiveOutputParseError(typeof event.data.output_parse_error === 'string' ? event.data.output_parse_error : null)
              setLiveResponseCommitted(true)
            }
            if (eventType === 'execution_failed' || eventType === 'execution_cancelled') {
              flushLiveAnswer(answer)
              setStopping(false)
            }
          },
          onHeartbeat: () => setLastHeartbeatAt(Date.now()),
        }, controller.signal)
        terminalObserved = true
        await refreshPersistedSession(active.network_session_id)
      } catch (error) {
        if (!controller.signal.aborted) {
          toast.warning(error instanceof Error ? error.message : 'Network Run resume failed')
        }
      } finally {
        const ownsObserver = abortRef.current === controller
        if (ownsObserver) abortRef.current = null
        if (executionIdRef.current === active.execution_id) executionIdRef.current = null
        if (terminalObserved && reattachExecutionRef.current === active.execution_id) {
          reattachExecutionRef.current = null
        }
        if (ownsObserver && mountedRef.current) clearLiveState()
      }
    })()

    return () => { disposed = true }
  }, [activeSession?.id, creatingSession, environment, networkId, onSelectSession, projectId, running, runtimeEnabled])

  const stop = () => {
    if (!running || stopping || stopRequestRef.current) return
    stopRequestRef.current = true
    const executionId = executionIdRef.current
    setStopping(true)
    if (!executionId) {
      stopIntentRef.current = true
      setLiveActivity((items) => [...items.slice(-5), 'Waiting for Network Run identity before stopping...'])
      return
    }
    requestCancellation(executionId)
  }

  const startNew = () => {
    if (running || creatingSession) return
    if (!runtimeEnabled) {
      toast.error(`${environment} Network runtime is off`)
      return
    }
    abortRef.current?.abort()
    abortRef.current = null
    executionIdRef.current = null
    clearLiveState()
    setLocalTurns([])
    setText('')
    onStartNewConversation()
  }

  const resetContext = async () => {
    if (running || creatingSession || !activeSession) return
    try {
      await resetNetworkSessionContext(networkId, activeSession.id, projectId)
      toast.success('Agent contexts reset for this Network Session')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to reset Network context')
    }
  }

  const send = async (suggestion?: string) => {
    const content = (suggestion ?? text).trim()
    if (!content || running || creatingSession) return
    if (!runtimeEnabled) {
      toast.error(`${environment} Network runtime is off`)
      return
    }
    if (changed) {
      toast.warning(`Start a new ${environment} Session for the current Network version before sending`)
      return
    }

    let session = activeSession
    let preparedDraftRevision: number | undefined
    if (!session) {
      setCreatingSession(true)
      try { session = await onCreateSession() } finally { setCreatingSession(false) }
      if (!session) return
      if (environment === 'draft') preparedDraftRevision = session.draftRevision ?? undefined
    }

    liveAnswerSchedulerRef.current?.clear()
    stopIntentRef.current = false
    stopRequestRef.current = false
    setText('')
    setRunning(true)
    setStopping(false)
    setPendingMessage(content)
    setLiveAnswer('')
    setLiveActivity([])
    setLiveExecution(emptyLiveNetworkExecution())
    setLiveResponseCommitted(false)
    setLiveParsedOutput(null)
    setLiveOutputParseError(null)
    setLastHeartbeatAt(null)
    shouldStickToBottomRef.current = true
    const controller = new AbortController()
    abortRef.current = controller
    const records: RuntimeEventRecord[] = []
    let answer = ''
    let executionId = ''
    let traceId = ''
    let status: NetworkExecution['status'] = 'success'

    try {
      const expectedDraftRevision = environment === 'draft' ? preparedDraftRevision ?? await onBeforeDraftRun() : undefined
      const executionBindings = environment === 'draft' ? Object.fromEntries(Object.entries(bindings).map(([nodeId, binding]) => [nodeId, { ...binding, version: `r${expectedDraftRevision}`, dirty: false }])) as Record<AgentNodeId, NetworkBinding> : bindings
      await streamNetworkExecution({ networkId, projectId, networkSessionId: session.id, message: content, expectedDraftRevision }, {
        onExecutionId: (id) => {
          executionId = id
          executionIdRef.current = id
          reattachExecutionRef.current = id
          if (stopIntentRef.current) requestCancellation(id)
        },
        onEvent: (eventType, event) => {
          if (!executionId && event.execution_id) {
            executionId = event.execution_id
            executionIdRef.current = event.execution_id
            reattachExecutionRef.current = event.execution_id
            if (stopIntentRef.current) requestCancellation(event.execution_id)
          }
          if (shouldRecordRuntimeEvent(eventType)) records.push({ eventType, event })
          if (updatesLiveExecution(eventType)) {
            setLiveExecution((current) => applyNetworkRuntimeEvent(current, eventType, event))
          }
          if (eventType !== 'token' && eventType !== 'token_retract' && eventType !== 'run.state') setLiveActivity((items) => [...items.slice(-5), activityLabel(eventType, event)])
          if (eventType === 'token' && isPublicFinalToken(event)) {
            const chunk = event.data.content
            if (typeof chunk === 'string') { answer += chunk; scheduleLiveAnswer(answer) }
          }
          if (eventType === 'token_retract') {
            const length = event.data.content_length
            if (typeof length === 'number' && length > 0) { answer = answer.slice(0, Math.max(0, answer.length - length)); scheduleLiveAnswer(answer) }
          }
          if (eventType === 'agent_invocation_completed' && !event.parent_invocation_id) {
            flushLiveAnswer(answer)
            setLiveParsedOutput(parsedOutputFromEvent(event))
            setLiveOutputParseError(typeof event.data.output_parse_error === 'string' ? event.data.output_parse_error : null)
            setLiveResponseCommitted(true)
          }
          if (eventType === 'execution_completed') {
            const id = event.data.trace_id
            if (typeof id === 'string') traceId = id
            flushLiveAnswer(answer)
            setLiveParsedOutput(parsedOutputFromEvent(event))
            setLiveOutputParseError(typeof event.data.output_parse_error === 'string' ? event.data.output_parse_error : null)
            setLiveResponseCommitted(true)
            setStopping(false)
          }
          if (eventType === 'execution_failed') {
            flushLiveAnswer(answer)
            status = 'error'
            setStopping(false)
          }
          if (eventType === 'execution_cancelled') {
            const output = event.data.output
            if (typeof output === 'string') answer = output
            flushLiveAnswer(answer)
            status = 'cancelled'
            setStopping(false)
          }
        },
        onHeartbeat: () => setLastHeartbeatAt(Date.now()),
      }, controller.signal)

      if (!executionId) throw new Error('Network stream completed without an execution identifier')
      const turn = buildTurnFromRuntimeEvents({ records, environment, bindings: executionBindings, executionId, user: content, answer, fallbackTraceId: traceId, terminalStatus: status })
      setLocalTurns((items) => [...items.filter((item) => item.id !== turn.id), turn])
      clearLiveState()
      onRun(createNetworkTraceRecord({ execution: turn.execution, environment, bindings: executionBindings, networkSessionId: session.id, title: content, userMessage: content, answer: turn.answer, usage: turn.usage, agentContexts: session.agentContexts, parsedOutput: turn.parsedOutput, source: 'chat', runtimeEvents: records, networkVersion: environment === 'draft' ? `Draft r${expectedDraftRevision}` : versionLabel }))
      await refreshPersistedSession(session.id)
    } catch (error) {
      if (!controller.signal.aborted) {
        if (!executionId) setText(content)
        toast.error(error instanceof Error ? error.message : 'Network execution failed')
        if (executionId) await refreshPersistedSession(session.id)
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      if (executionIdRef.current === executionId) executionIdRef.current = null
      clearLiveState()
    }
  }

  const disabledReason = runtimeEnabled ? undefined : `${environment.charAt(0).toUpperCase() + environment.slice(1)} runtime is off. Inspection and release management remain available.`

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <NetworkChatHeader environment={environment} versionLabel={versionLabel} counts={counts} sessions={sessions} activeSessionId={activeSession?.id ?? null} changed={changed} newSessionDisabled={running || creatingSession || !runtimeEnabled} onSelectSession={onSelectSession} onNew={startNew} onResetContext={() => void resetContext()} />
      {historyLoading ? <div className="border-b border-border/60 px-4 py-2 text-[9px] text-muted">Loading persisted Network history…</div> : null}
      {!runtimeEnabled ? <div className="border-b border-red-500/20 bg-red-500/5 px-4 py-2 text-[9px] font-medium text-red-300">{disabledReason}</div> : null}
      <NetworkChatHistory scrollRef={scrollRef} networkName={networkName} turns={turns} running={running} pendingMessage={pendingMessage} liveAnswer={liveAnswer} liveActivity={liveActivity} liveExecution={liveExecution} liveResponseCommitted={liveResponseCommitted} liveParsedOutput={liveParsedOutput} liveOutputParseError={liveOutputParseError} onScroll={(event) => { shouldStickToBottomRef.current = isNearBottom(event.currentTarget) }} onSuggestion={send} onSelectAgent={onSelectAgent} onOpenTrace={onOpenTrace} />
      {running ? <div className="mx-4 mb-2 text-right text-[9px] text-muted">{stopping ? 'Stopping… waiting for finalization' : lastHeartbeatAt ? 'Runtime heartbeat received' : 'Runtime connection open'}</div> : null}
      <NetworkChatComposer value={text} running={running} stopping={stopping} preparing={creatingSession} disabled={!runtimeEnabled} disabledReason={disabledReason} onChange={setText} onSend={() => { void send() }} onStop={stop} />
    </div>
  )
}
