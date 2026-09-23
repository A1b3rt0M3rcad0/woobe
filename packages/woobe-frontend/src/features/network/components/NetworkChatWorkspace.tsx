import { isSkillOperation, operationLabel } from '@/features/skills/operations'
import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { ChatCanvas, type ChatCanvasEntry } from '@/features/playground/components/ChatCanvas'
import { filterContractValues, filterExternalContextInput } from '@/features/contracts/contractFields'
import type { Agent } from '@/features/agents/types'
import type { ChatMessage as PlaygroundChatMessage } from '@/features/playground/types'
import { cancelNetworkExecution } from '@/features/network/api'
import { useNetworkExternalContextContract, useNetworkRuntimeEnvironments } from '@/features/network/hooks'
import { useNetworkIdentity } from '@/features/network/NetworkIdentityContext'
import { getActiveNetworkExecution } from '@/features/network/runtime-reattach-api'
import { streamNetworkExecution } from '@/features/network/stream'
import { previewNetworkDraftExternalContextContract } from '@/features/network/externalContextContractPreview'
import type { NetworkDefinition, NetworkRuntimeEvent } from '@/features/network/types'
import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import { buildTurnFromRuntimeEvents, type NetworkExecution, type NetworkTurn, type RuntimeEventRecord } from './networkChatExecution'
import {
  networkTurnChatMessage,
  NetworkLiveDetails,
  NetworkOpenRunAction,
  NetworkTurnDetails,
  NetworkTurnFooterMeta,
} from './NetworkExecutionTree'
import { createNetworkLiveAnswerScheduler } from './networkLiveAnswerScheduler'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { applyNetworkRuntimeEvent, emptyLiveNetworkExecution } from './networkLiveExecution'
import {
  persistedTurnSupersedesLocal,
  reconcileNetworkTurns,
} from './networkTurnReconciliation'

interface NetworkChatWorkspaceProps {
  networkId: string
  projectId: string
  networkName: string
  environment: Environment
  versionLabel: string
  currentVersionId: string | null
  bindings: Record<AgentNodeId, NetworkBinding>
  draftDefinition: NetworkDefinition
  agents: Agent[]
  liveDraftContractsByAgentId: Record<string, unknown>
  historyBindings: Record<AgentNodeId, NetworkBinding>
  historyVersionLabel: string
  activeSession: NetworkSession | null
  historyTurns: NetworkTurn[]
  historyLoading: boolean
  onBeforeDraftRun: () => Promise<number>
  onSelectSession: (sessionId: string) => void
  onCreateSession: () => Promise<NetworkSession | null>
  onStartNewConversation: () => void
  onSessionActionBlockedChange?: (blocked: boolean) => void
  onRun: (trace: NetworkTraceRecord) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

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

const EMPTY_EXTERNAL_CONTEXT_CONTRACT: Record<string, never> = {}

const networkSuggestions = [
  'Test a request that should be answered by the entry Agent.',
  'Test a request that should require delegation to a specialist.',
  'Test the complete Network composition with a realistic user request.',
]

function activityLabel(eventType: string, event: NetworkRuntimeEvent) {
  if (eventType === 'execution_accepted') return `Execution accepted in ${String(event.data.environment ?? 'runtime')}`
  if (eventType === 'execution_started') return 'Network worker started the execution'
  if (eventType === 'agent_activity') return String(event.data.message ?? event.data.status ?? 'Agent is working')
  if (eventType === 'agent_invocation_started') return `Agent started: ${String(event.data.label ?? event.agent_id ?? 'unknown')}`
  if (eventType === 'agent_invocation_completed') return `Agent completed at depth ${event.depth ?? 0}`
  if (eventType === 'agent_invocation_failed') return `Agent failed: ${String(event.data.message ?? event.data.code ?? 'runtime error')}`
  if (eventType === 'agent_invocation_cancelled') return `Agent cancelled at depth ${event.depth ?? 0}`
  if (['tool_call_started', 'tool_call_completed'].includes(eventType) && isSkillOperation({ tool_name: String(event.data.tool_name ?? '') })) return `${operationLabel({ ...event.data, tool_name: String(event.data.tool_name) })} · ${eventType === 'tool_call_started' ? 'running' : event.data.success === false ? 'failed' : 'completed'}`
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

export function NetworkChatWorkspace({
  networkId,
  projectId,
  networkName,
  environment,
  versionLabel,
  currentVersionId,
  bindings,
  draftDefinition,
  agents,
  liveDraftContractsByAgentId,
  historyBindings,
  historyVersionLabel,
  activeSession,
  historyTurns,
  historyLoading,
  onBeforeDraftRun,
  onSelectSession,
  onCreateSession,
  onSessionActionBlockedChange,
  onRun,
  onSelectAgent,
  onOpenTrace,
}: NetworkChatWorkspaceProps) {
  const queryClient = useQueryClient()
  const exactNetworkName = useNetworkIdentity() ?? networkName
  const runtimeStatesQuery = useNetworkRuntimeEnvironments(networkId, projectId)
  const externalContextContractQuery = useNetworkExternalContextContract(networkId, projectId, environment)
  const runtimeEnabled = runtimeStatesQuery.data?.[environment]?.enabled ?? true
  const persistedExternalContextContract = externalContextContractQuery.data ?? EMPTY_EXTERNAL_CONTEXT_CONTRACT
  const effectiveExternalContextContract = useMemo(
    () => environment === 'draft'
      ? previewNetworkDraftExternalContextContract({
          persistedEffectiveContract: persistedExternalContextContract,
          definition: draftDefinition,
          agents,
          liveDraftContractsByAgentId,
        })
      : persistedExternalContextContract,
    [
      agents,
      draftDefinition,
      environment,
      liveDraftContractsByAgentId,
      persistedExternalContextContract,
    ],
  )
  const storedEnvironmentContext = runtimeStatesQuery.data?.[environment]?.external_context_values
  const [externalContextValues, setExternalContextValues] = useState<Record<string, unknown>>({})
  const externalContextOwnerRef = useRef<string | null>(null)
  const externalContextDirtyRef = useRef(false)
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
  const abortRef = useRef<AbortController | null>(null)
  const executionIdRef = useRef<string | null>(null)
  const stopIntentRef = useRef(false)
  const stopRequestRef = useRef(false)
  const reattachExecutionRef = useRef<string | null>(null)
  const previousSessionIdRef = useRef<string | null>(activeSession?.id ?? null)
  const onSelectSessionRef = useRef(onSelectSession)
  const mountedRef = useRef(true)
  const liveAnswerSchedulerRef = useRef<ReturnType<typeof createNetworkLiveAnswerScheduler> | null>(null)
  if (liveAnswerSchedulerRef.current === null) liveAnswerSchedulerRef.current = createNetworkLiveAnswerScheduler(setLiveAnswer)

  const changed = Boolean(activeSession && environment !== 'draft' && activeSession.networkVersion !== currentVersionId)
  const lockedExternalContextValues = activeSession?.externalContextSnapshot ?? {}
  const turns = useMemo(() => reconcileNetworkTurns(historyTurns, localTurns), [historyTurns, localTurns])

  useLayoutEffect(() => {
    const environmentValues = filterContractValues(
      effectiveExternalContextContract,
      storedEnvironmentContext,
    )
    const previousEnvironment = externalContextOwnerRef.current
    const contextDirty = externalContextDirtyRef.current

    setExternalContextValues((current) => {
      const currentValues = filterContractValues(effectiveExternalContextContract, current)
      if (previousEnvironment === null || previousEnvironment !== environment) {
        return environmentValues
      }
      return contextDirty ? currentValues : environmentValues
    })

    if (previousEnvironment !== environment) externalContextDirtyRef.current = false
    externalContextOwnerRef.current = environment
  }, [
    effectiveExternalContextContract,
    environment,
    storedEnvironmentContext,
  ])

  const handleExternalContextValuesChange = useCallback((values: Record<string, unknown>) => {
    externalContextDirtyRef.current = true
    setExternalContextValues(filterContractValues(effectiveExternalContextContract, values))
  }, [effectiveExternalContextContract])

  useLayoutEffect(() => {
    onSelectSessionRef.current = onSelectSession
  }, [onSelectSession])

  useLayoutEffect(() => {
    onSessionActionBlockedChange?.(running || creatingSession || !runtimeEnabled)
  }, [creatingSession, onSessionActionBlockedChange, running, runtimeEnabled])

  useLayoutEffect(() => () => {
    onSessionActionBlockedChange?.(false)
  }, [onSessionActionBlockedChange])

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

  useLayoutEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      liveAnswerSchedulerRef.current?.clear()
      abortRef.current?.abort()
      abortRef.current = null
    }
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
    if (!historyTurns.length) return
    const persistedById = new Map(historyTurns.map((turn) => [turn.id, turn]))
    setLocalTurns((current) => current.filter((local) => {
      const persisted = persistedById.get(local.id)
      return !persisted || !persistedTurnSupersedesLocal(persisted, local)
    }))
  }, [historyTurns])

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
        onSelectSessionRef.current(active.network_session_id)
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

      const controller = new AbortController()
      abortRef.current = controller
      const records: RuntimeEventRecord[] = []
      const reattachBindings = Object.keys(historyBindings).length ? historyBindings : bindings
      let answer = ''
      let traceId = ''
      let status: NetworkExecution['status'] = 'success'
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
            if (shouldRecordRuntimeEvent(eventType)) records.push({ eventType, event })
            if (updatesLiveExecution(eventType)) setLiveExecution((current) => applyNetworkRuntimeEvent(current, eventType, event))
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
              const id = event.data.trace_id
              if (typeof id === 'string') traceId = id
              const output = event.data.output
              if (typeof output === 'string' && output) answer = output
              status = 'success'
              flushLiveAnswer(answer)
              setLiveParsedOutput(parsedOutputFromEvent(event))
              setLiveOutputParseError(typeof event.data.output_parse_error === 'string' ? event.data.output_parse_error : null)
              setLiveResponseCommitted(true)
              setStopping(false)
            }
            if (eventType === 'execution_failed') {
              const id = event.data.trace_id
              if (typeof id === 'string') traceId = id
              status = 'error'
              flushLiveAnswer(answer)
              setStopping(false)
            }
            if (eventType === 'execution_cancelled') {
              const id = event.data.trace_id
              if (typeof id === 'string') traceId = id
              const output = event.data.output
              if (typeof output === 'string') answer = output
              status = 'cancelled'
              flushLiveAnswer(answer)
              setStopping(false)
            }
          },
          onHeartbeat: () => setLastHeartbeatAt(Date.now()),
        }, controller.signal)
        terminalObserved = true
        const turn = buildTurnFromRuntimeEvents({
          records,
          environment,
          bindings: reattachBindings,
          executionId: active.execution_id,
          user: active.input_message,
          answer,
          fallbackTraceId: traceId,
          terminalStatus: status,
        })
        setLocalTurns((items) => [...items.filter((item) => item.id !== turn.id), turn])
        onRun(createNetworkTraceRecord({
          execution: turn.execution,
          environment,
          bindings: reattachBindings,
          networkSessionId: active.network_session_id,
          title: active.input_message,
          userMessage: active.input_message,
          answer: turn.answer,
          usage: turn.usage,
          agentContexts: activeSession.agentContexts,
          parsedOutput: turn.parsedOutput,
          outputParseError: turn.outputParseError,
          source: 'runtime',
          runtimeEvents: records,
          networkVersion: historyVersionLabel,
        }))
        await refreshPersistedSession(active.network_session_id)
      } catch (error) {
        if (!controller.signal.aborted) toast.warning(error instanceof Error ? error.message : 'Network Run resume failed')
      } finally {
        const ownsObserver = abortRef.current === controller
        if (ownsObserver) abortRef.current = null
        if (executionIdRef.current === active.execution_id) executionIdRef.current = null
        // Keep a successfully observed terminal execution as a local tombstone. This
        // prevents a stale SQL active lookup from reopening the same Run while the
        // asynchronous journal projector catches up. Transport failures clear the
        // tombstone so a later discovery can retry the observer.
        if (!terminalObserved && reattachExecutionRef.current === active.execution_id) {
          reattachExecutionRef.current = null
        }
        if (ownsObserver && mountedRef.current) clearLiveState()
      }
    })()

    return () => { disposed = true }
  }, [activeSession?.id, creatingSession, environment, historyBindings, historyVersionLabel, networkId, projectId, running, runtimeEnabled])

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

  const send = async (content: string) => {
    const message = content.trim()
    if (!message || running || creatingSession) return
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
    setPendingMessage(message)
    setLiveAnswer('')
    setLiveActivity([])
    setLiveExecution(emptyLiveNetworkExecution())
    setLiveResponseCommitted(false)
    setLiveParsedOutput(null)
    setLiveOutputParseError(null)
    setLastHeartbeatAt(null)
    const controller = new AbortController()
    abortRef.current = controller
    const records: RuntimeEventRecord[] = []
    let answer = ''
    let executionId = ''
    let traceId = ''
    let status: NetworkExecution['status'] = 'success'

    try {
      const expectedDraftRevision = environment === 'draft' ? preparedDraftRevision ?? await onBeforeDraftRun() : undefined
      const executionBindings = environment === 'draft'
        ? Object.fromEntries(Object.entries(bindings).map(([nodeId, binding]) => [nodeId, { ...binding, version: `r${expectedDraftRevision}`, dirty: false }])) as Record<AgentNodeId, NetworkBinding>
        : bindings
      await streamNetworkExecution({
        networkId,
        projectId,
        networkSessionId: session.id,
        message,
        expectedDraftRevision,
        externalContext: filterExternalContextInput(
          effectiveExternalContextContract,
          externalContextValues,
          session.externalContextSnapshot ?? {},
        ),
      }, {
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
          if (updatesLiveExecution(eventType)) setLiveExecution((current) => applyNetworkRuntimeEvent(current, eventType, event))
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
      const turn = buildTurnFromRuntimeEvents({ records, environment, bindings: executionBindings, executionId, user: message, answer, fallbackTraceId: traceId, terminalStatus: status })
      setLocalTurns((items) => [...items.filter((item) => item.id !== turn.id), turn])
      clearLiveState()
      onRun(createNetworkTraceRecord({
        execution: turn.execution,
        environment,
        bindings: executionBindings,
        networkSessionId: session.id,
        title: message,
        userMessage: message,
        answer: turn.answer,
        usage: turn.usage,
        agentContexts: session.agentContexts,
        parsedOutput: turn.parsedOutput,
        source: 'chat',
        runtimeEvents: records,
        networkVersion: environment === 'draft' ? `Draft r${expectedDraftRevision}` : versionLabel,
      }))
      await refreshPersistedSession(session.id)
    } catch (error) {
      if (!controller.signal.aborted) {
        if (!executionId) setText(message)
        toast.error(error instanceof Error ? error.message : 'Network execution failed')
        await refreshPersistedSession(session.id)
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      if (executionIdRef.current === executionId) executionIdRef.current = null
      clearLiveState()
    }
  }

  const chatEntries = useMemo<ChatCanvasEntry[]>(() => {
    const entries: ChatCanvasEntry[] = []

    for (const turn of turns) {
      entries.push({
        key: `${turn.id}:user`,
        message: { role: 'user', content: turn.user },
      })
      entries.push({
        key: `${turn.id}:assistant`,
        message: networkTurnChatMessage(turn),
        agentName: exactNetworkName,
        assistantIcon: 'network',
        details: <NetworkTurnDetails turn={turn} onSelectAgent={onSelectAgent} />,
        footerMeta: <NetworkTurnFooterMeta turn={turn} />,
        footerActions: <NetworkOpenRunAction execution={turn.execution} onOpenTrace={onOpenTrace} />,
        className: turn.execution.status === 'error' ? 'rounded-xl border border-red-500/25 bg-red-500/[0.03] p-2' : undefined,
      })
    }

    if (running && pendingMessage) {
      const liveMessage: PlaygroundChatMessage = {
        role: 'assistant',
        content: liveAnswer,
        parsed_output: liveParsedOutput,
        output_parse_error: liveOutputParseError,
        activity: liveAnswer
          ? null
          : {
              status: 'working',
              message: liveActivity[liveActivity.length - 1] ?? 'Executing Network composition…',
            },
        tool_calls: liveExecution.tools,
        sources: liveExecution.sources,
      }
      entries.push({ key: 'live:user', message: { role: 'user', content: pendingMessage } })
      entries.push({
        key: 'live:assistant',
        message: liveMessage,
        agentName: exactNetworkName,
        assistantIcon: 'network',
        isStreaming: !liveResponseCommitted,
        details: <NetworkLiveDetails delegations={liveExecution.delegations} agents={liveExecution.agents} onSelectAgent={onSelectAgent} />,
      })
    }

    return entries
  }, [
    exactNetworkName,
    liveActivity,
    liveAnswer,
    liveExecution.agents,
    liveExecution.delegations,
    liveExecution.sources,
    liveExecution.tools,
    liveOutputParseError,
    liveParsedOutput,
    liveResponseCommitted,
    onOpenTrace,
    onSelectAgent,
    pendingMessage,
    running,
    turns,
  ])

  const disabledReason = runtimeEnabled
    ? undefined
    : `${environment.charAt(0).toUpperCase() + environment.slice(1)} runtime is off. Inspection and release management remain available.`
  const snapshotReason = changed
    ? `This Session belongs to an earlier ${environment} snapshot. Use New Session to continue on the current Network version.`
    : undefined
  const runtimeBlockReason = disabledReason ?? snapshotReason
  const composerStatusText = running
    ? lastHeartbeatAt ? 'Network Run active · runtime heartbeat received' : 'Network Run active'
    : undefined

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ChatCanvas
        entries={chatEntries}
        isSending={running}
        isStopping={stopping}
        isPreparing={creatingSession}
        isSessionLoading={historyLoading}
        onSend={(content) => { void send(content) }}
        onStop={stop}
        assistantIcon="network"
        runtimeBlocked={Boolean(runtimeBlockReason)}
        runtimeBlockReason={runtimeBlockReason}
        emptyTitle="Test your Network"
        emptyDescription="Every message starts at the entry Agent and executes the current Network composition."
        suggestions={networkSuggestions}
        composerValue={text}
        onComposerValueChange={setText}
        composerStatusText={composerStatusText}
        preparingText="Preparing Network Session..."
        enableFirstRunSuccess={false}
        externalContextContract={effectiveExternalContextContract}
        externalContextValues={externalContextValues}
        lockedExternalContextValues={lockedExternalContextValues}
        onExternalContextValuesChange={handleExternalContextValuesChange}
      />
    </div>
  )
}
