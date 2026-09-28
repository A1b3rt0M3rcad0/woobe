import { useCallback, useEffect, useRef } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createSession,
  ask,
  getSessionMessages,
} from './api'
import { cancelAgentRun } from './reattach-api'
import { getAgentSessionsByEnvironment } from './session-api'
import { askStreamV1, reattachAgentRunV1, type StreamCallbacks } from './stream-client'
import { createAgentStreamCancellationCoordinator } from './stream-cancellation'
import { resetAgentStreamStopState, setAgentStreamStopState } from './stream-stop-state'
import type { RuntimeEnvironment } from '@/features/agents/types'
import type { CreateSessionRequest, AskRequest } from './types'

let activeStreamController: AbortController | null = null

const AGENT_SESSIONS_PAGE_SIZE = 20
const DEFAULT_OUTPUT_CONTRACT = { message: 'string', confidence: 'float' }
const TERMINAL_AGENT_RUN_STATUSES = new Set(['completed', 'failed', 'cancelled', 'timed_out', 'uncertain'])

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function hasMaterializedSchema(schema: unknown): boolean {
  if (typeof schema === 'string') return schema.trim().length > 0
  return Boolean(schema && typeof schema === 'object')
}

function withStrictOutputContract(data: AskRequest): AskRequest {
  const snapshot = data.snapshot_override
  if (!snapshot) return data
  const responseFormat = recordValue(snapshot.response_format)
  if (Object.keys(responseFormat).length === 0) return data
  const jsonEnabled = responseFormat.enabled === true && responseFormat.type === 'json'
  const schema = jsonEnabled && !hasMaterializedSchema(responseFormat.schema)
    ? DEFAULT_OUTPUT_CONTRACT
    : responseFormat.schema
  return {
    ...data,
    snapshot_override: {
      ...snapshot,
      response_format: {
        ...responseFormat,
        strict: true,
        schema,
      },
      output_schema: schema,
    },
  }
}

export function cancelActiveAskStream() {
  activeStreamController?.abort()
}

export function shouldRefreshAgentRunList(
  previousRunId: string | null,
  nextRunId: string | null | undefined,
): boolean {
  return Boolean(nextRunId && previousRunId !== nextRunId)
}

export interface AgentStreamStopCallbacks {
  onDispatched?: (runId: string) => void
  onConfirmed?: (runId: string) => void
  onError?: (runId: string, error: Error) => void
}

export function useCreateSession() {
  return useMutation({ mutationFn: (data: CreateSessionRequest) => createSession(data) })
}

export function useAsk() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AskRequest) => ask(withStrictOutputContract(data)),
    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: ['project-overview'],
        refetchType: 'none',
      })
    },
  })
}

export function useAgentSessions(
  agentId: string | undefined,
  projectId: string | undefined,
  environment: RuntimeEnvironment = 'draft',
) {
  return useInfiniteQuery({
    queryKey: ['agent-sessions', agentId, projectId, environment],
    queryFn: ({ pageParam }) => getAgentSessionsByEnvironment(agentId!, projectId!, environment, {
      limit: AGENT_SESSIONS_PAGE_SIZE,
      cursor: pageParam,
    }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.has_next ? lastPage.next_cursor : undefined,
    enabled: !!agentId && !!projectId,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  })
}

export function useSessionMessages(sessionId: string | undefined) {
  return useQuery({
    queryKey: ['session-messages', sessionId],
    queryFn: () => getSessionMessages(sessionId!),
    enabled: !!sessionId,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}

export function useAskStream() {
  const queryClient = useQueryClient()
  const activeSessionIdRef = useRef<string | null>(null)
  const refreshedRunIdRef = useRef<string | null>(null)
  const ownedStreamControllerRef = useRef<AbortController | null>(null)
  const stopCallbacksRef = useRef<AgentStreamStopCallbacks>({})
  const cancellationRef = useRef<ReturnType<typeof createAgentStreamCancellationCoordinator> | null>(null)
  if (cancellationRef.current === null) {
    cancellationRef.current = createAgentStreamCancellationCoordinator(cancelAgentRun, {
      onDispatch: (runId) => {
        setAgentStreamStopState('stopping')
        stopCallbacksRef.current.onDispatched?.(runId)
      },
      onConfirmed: (runId) => stopCallbacksRef.current.onConfirmed?.(runId),
      onError: (runId, error) => {
        setAgentStreamStopState('running')
        stopCallbacksRef.current.onError?.(runId, error)
      },
    })
  }
  const cancellation = cancellationRef.current

  useEffect(() => () => {
    const controller = ownedStreamControllerRef.current
    if (controller && !controller.signal.aborted) controller.abort()
  }, [])

  const reconcileCallbacks = useCallback((callbacks: StreamCallbacks): StreamCallbacks => ({
    ...callbacks,
    onMeta: (meta) => {
      if (meta.run_id) {
        cancellation.observeRun(meta.run_id)
        // run.state can re-publish the same identity during reattach/reconciliation.
        // Refresh the SQL Run list once per owned Run instead of turning those
        // frames into extra HTTP requests while SSE is already authoritative.
        if (shouldRefreshAgentRunList(refreshedRunIdRef.current, meta.run_id)) {
          refreshedRunIdRef.current = meta.run_id
          void queryClient.invalidateQueries({ queryKey: ['agent-runs'] })
        }
      }
      if (meta.session_id) activeSessionIdRef.current = meta.session_id
      callbacks.onMeta(meta)
    },
    onRunState: (state) => {
      const status = typeof state.status === 'string' ? state.status : ''
      if (status === 'cancel_requested') setAgentStreamStopState('stopping')
      else if (TERMINAL_AGENT_RUN_STATUSES.has(status)) resetAgentStreamStopState()
      else if (status === 'running') setAgentStreamStopState('running')
      callbacks.onRunState?.(state)
    },
    onDone: (response) => {
      resetAgentStreamStopState()
      callbacks.onDone(response)
    },
    onError: (error) => {
      resetAgentStreamStopState()
      callbacks.onError(error)
    },
    onCancelled: (event) => {
      resetAgentStreamStopState()
      callbacks.onCancelled?.(event)
    },
  }), [cancellation, queryClient])

  const withController = useCallback(async (
    operation: (signal: AbortSignal) => Promise<void>,
  ) => {
    activeStreamController?.abort()
    const controller = new AbortController()
    activeStreamController = controller
    ownedStreamControllerRef.current = controller
    try {
      await operation(controller.signal)
    } finally {
      const observedSessionId = activeSessionIdRef.current
      const ownsCurrentStream = activeStreamController === controller
      if (ownsCurrentStream) {
        activeStreamController = null
        cancellation.finish()
        stopCallbacksRef.current = {}
        activeSessionIdRef.current = null
        resetAgentStreamStopState()
      }
      if (ownedStreamControllerRef.current === controller) {
        ownedStreamControllerRef.current = null
      }
      // An aborted/replaced observer did not finish the Run. In particular, its
      // cleanup must not refetch the Session now owned by a newer controller.
      if (ownsCurrentStream && !controller.signal.aborted) {
        if (observedSessionId) {
          void queryClient.invalidateQueries({ queryKey: ['session-messages', observedSessionId] })
        }
        void queryClient.invalidateQueries({ queryKey: ['agent-sessions'] })
        void queryClient.invalidateQueries({ queryKey: ['agent-runs'] })
        void queryClient.invalidateQueries({ queryKey: ['traces'] })
        void queryClient.invalidateQueries({
          queryKey: ['project-overview'],
          refetchType: 'none',
        })
      }
    }
  }, [cancellation, queryClient])

  const stream = useCallback(async (
    data: AskRequest,
    callbacks: StreamCallbacks,
  ) => {
    activeSessionIdRef.current = data.session_id ?? null
    refreshedRunIdRef.current = null
    stopCallbacksRef.current = {}
    setAgentStreamStopState('running')
    cancellation.begin()
    return withController(
      (signal) => askStreamV1(
        withStrictOutputContract(data),
        reconcileCallbacks(callbacks),
        signal,
      ),
    )
  }, [cancellation, reconcileCallbacks, withController])

  const reattach = useCallback(async (
    runId: string,
    callbacks: StreamCallbacks,
  ) => {
    activeSessionIdRef.current = null
    stopCallbacksRef.current = {}
    setAgentStreamStopState('running')
    cancellation.begin(runId)
    return withController(
      (signal) => reattachAgentRunV1(runId, reconcileCallbacks(callbacks), signal),
    )
  }, [cancellation, reconcileCallbacks, withController])

  // Stop is a Run command, not a transport disconnect. The active observer remains
  // attached until the runtime emits its durable terminal cancellation event.
  const cancel = useCallback((callbacks: AgentStreamStopCallbacks = {}) => {
    stopCallbacksRef.current = callbacks
    const accepted = cancellation.requestStop()
    if (accepted) setAgentStreamStopState('stopping')
    else stopCallbacksRef.current = {}
    return accepted
  }, [cancellation])

  // Navigation/unmount only disposes this hook's observer. The Run remains owned by
  // the runtime and can be recovered through the active-run/reattach contract.
  const disconnect = useCallback(() => {
    ownedStreamControllerRef.current?.abort()
  }, [])

  return { stream, reattach, cancel, disconnect }
}
