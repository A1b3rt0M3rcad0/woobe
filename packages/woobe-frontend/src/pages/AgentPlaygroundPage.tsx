import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent, useAgentRuntimeEnvironments, useReleases } from '@/features/agents/hooks'
import { useAgentEditorSection } from '@/features/agents/components/AgentEditorNavigation'
import { validateAgentEditorState } from '@/features/agents/editorValidation'
import type { RuntimeEnvironment } from '@/features/agents/types'
import { usePlaygroundTraces } from '@/features/traces/hooks'
import { useAskStream, useAgentSessions, useCreateSession, useSessionMessages } from '@/features/playground/hooks'
import { getActiveAgentRun } from '@/features/playground/reattach-api'
import { ErrorState } from '@/components/common/ErrorState'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { PlaygroundHeader } from '@/features/playground/components/PlaygroundHeader'
import { OperationsRail, type LeftPanelTab } from '@/features/playground/components/OperationsRail'
import { OperationsPanel } from '@/features/playground/components/OperationsPanel'
import { ChatCanvas } from '@/features/playground/components/ChatCanvas'
import { filterContractValues } from '@/features/contracts/contractFields'
import { AgentInspector } from '@/features/playground/components/AgentInspector'
import { ApiModal } from '@/features/playground/components/ApiModal'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import {
  getStoredPlaygroundExternalContext,
  getStoredPlaygroundRunId,
  getStoredPlaygroundSessionId,
  setPlaygroundSessionId,
  setStoredPlaygroundExternalContext,
  setStoredPlaygroundRunId,
  setStoredPlaygroundSessionId,
} from '@/features/playground/lib/playground-session-store'
import { useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { AssistantMessageInfo, AskRequest, AskResponse, ChatMessage, TraceItem, RawStreamEvent, ToolCallInfo, SessionListItem, SessionListPage } from '@/features/playground/types'

function titleCaseEnvironment(environment: RuntimeEnvironment) {
  return environment.charAt(0).toUpperCase() + environment.slice(1)
}

function sessionEnvironment(item: SessionListItem): RuntimeEnvironment {
  const value = item.runtime_environment
  return value === 'staging' || value === 'production' || value === 'draft' ? value : 'draft'
}

function traceEnvironment(data: Record<string, unknown>): RuntimeEnvironment {
  const value = data.execution_context
  if (value === 'staging' || value === 'production') return value
  return 'draft'
}

function upsertToolCall(existing: ToolCallInfo[] | null | undefined, next: ToolCallInfo): ToolCallInfo[] {
  const items = existing ? [...existing] : []
  const index = next.tool_call_id ? items.findIndex((item) => item.tool_call_id === next.tool_call_id) : -1
  if (index === -1) return [...items, next]
  items[index] = { ...items[index], ...next, input: next.input ?? items[index].input, output: next.output ?? items[index].output }
  return items
}

function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-full bg-white/[0.07] ${className}`} />
}

function AgentPlaygroundSkeleton() {
  return (
    <div className="-m-6 h-[calc(100vh-3.5rem)] overflow-hidden flex flex-col bg-background">
      <div className="h-12 shrink-0 border-b border-border bg-surface/60 px-3">
        <div className="flex h-full items-center gap-3">
          <SkeletonLine className="h-3 w-16" />
          <div className="h-5 w-px bg-border" />
          <SkeletonLine className="h-4 w-24" />
          <SkeletonLine className="h-5 w-20" />
          <div className="ml-auto flex items-center gap-2">
            <SkeletonLine className="h-7 w-24" />
            <SkeletonLine className="h-7 w-20" />
          </div>
        </div>
      </div>
      <div className="h-6 shrink-0 border-b border-border bg-surface/30 px-4">
        <div className="flex h-full items-center gap-2">
          <SkeletonLine className="h-2.5 w-28" />
          <SkeletonLine className="h-2.5 w-20" />
          <SkeletonLine className="ml-auto h-2.5 w-24" />
        </div>
      </div>
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className="w-[52px] shrink-0 border-r border-border bg-surface/75 p-2">
          <div className="space-y-2">
            <div className="h-10 animate-pulse rounded-lg border border-primary/15 bg-primary/5" />
            <div className="h-10 animate-pulse rounded-lg bg-white/[0.035]" />
            <div className="h-10 animate-pulse rounded-lg bg-white/[0.035]" />
          </div>
        </div>
        <div className="w-[400px] shrink-0 border-r border-border bg-surface/70 p-4">
          <SkeletonLine className="h-3 w-20" />
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-border/70 bg-background/35 p-3">
              <SkeletonLine className="h-3 w-24" />
              <SkeletonLine className="mt-3 h-2.5 w-full" />
              <SkeletonLine className="mt-2 h-2.5 w-4/5" />
            </div>
            <div className="rounded-xl border border-border/70 bg-background/35 p-3">
              <SkeletonLine className="h-3 w-28" />
              <SkeletonLine className="mt-3 h-2.5 w-full" />
              <SkeletonLine className="mt-2 h-2.5 w-2/3" />
            </div>
          </div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col bg-background">
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <div className="w-full max-w-sm space-y-4 text-center">
              <div className="mx-auto h-12 w-12 animate-pulse rounded-full border border-primary/20 bg-primary/10" />
              <SkeletonLine className="mx-auto h-3.5 w-64" />
              <SkeletonLine className="mx-auto h-2.5 w-56" />
            </div>
          </div>
          <div className="shrink-0 border-t border-border/70 p-4">
            <div className="h-12 animate-pulse rounded-xl border border-border bg-surface/55" />
          </div>
        </div>
        <div className="w-[400px] shrink-0 border-l border-border bg-surface/75">
          <div className="border-b border-border/90 px-3 py-3"><SkeletonLine className="h-3 w-20" /></div>
          <div className="space-y-3 p-4">
            <SkeletonLine className="h-3 w-24" />
            <div className="rounded-xl border border-border/70 bg-background/35 p-3">
              <SkeletonLine className="h-3 w-32" />
              <SkeletonLine className="mt-3 h-2.5 w-full" />
              <SkeletonLine className="mt-2 h-2.5 w-3/4" />
            </div>
            <div className="rounded-xl border border-border/70 bg-background/35 p-3">
              <SkeletonLine className="h-3 w-28" />
              <SkeletonLine className="mt-3 h-2.5 w-full" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function PlaygroundContent() {
  const { workspaceId, projectId, agentId } = useParams<{ workspaceId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)
  const { data: releases = [], isLoading: releasesLoading } = useReleases(agentId)
  const runtimeStatesQuery = useAgentRuntimeEnvironments(agentId, projectId)
  const { state, isDirty } = useAgentEditor()
  const [, setEditorSection] = useAgentEditorSection()
  const { stream, reattach, cancel: cancelStream, disconnect: disconnectStream } = useAskStream()
  const queryClient = useQueryClient()
  const { mutateAsync: createRuntimeSession, isPending: creatingSession } = useCreateSession()
  const [environment, setEnvironment] = useState<RuntimeEnvironment>('draft')

  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)
  const stagingRelease = useMemo(() => releases.find((release) => release.status === 'staging') ?? null, [releases])
  const productionRelease = useMemo(() => releases.find((release) => release.status === 'production') ?? null, [releases])
  const currentEnvironmentRelease = environment === 'staging' ? stagingRelease : environment === 'production' ? productionRelease : null
  const activeExternalContextContract = environment === 'draft'
    ? state.externalContextContract
    : currentEnvironmentRelease?.external_context_contract ?? null
  const storedEnvironmentContext = runtimeStatesQuery.data?.[environment]?.external_context_values

  const {
    data: sessionPages,
    refetch: refetchSessions,
    fetchNextPage: fetchNextSessionsPage,
    hasNextPage: hasMoreSessions,
    isLoading: sessionsLoading,
    isFetching: sessionsFetching,
    isFetchingNextPage: sessionsLoadingMore,
    isError: sessionsError,
    error: sessionsQueryError,
  } = useAgentSessions(agentId, projectId, environment)

  const releaseVersionById = useMemo(
    () => new Map(releases.map((release) => [release.id, release.version])),
    [releases],
  )

  const sessions = useMemo(() => {
    const byId = new Map<string, SessionListItem>()
    for (const page of sessionPages?.pages ?? []) {
      for (const item of page.items) {
        if (byId.has(item.id) || sessionEnvironment(item) !== environment) continue
        byId.set(item.id, {
          ...item,
          opened_release_version: item.opened_release_id ? releaseVersionById.get(item.opened_release_id) ?? null : null,
        })
      }
    }
    return Array.from(byId.values())
  }, [environment, releaseVersionById, sessionPages])

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [activeSessionIdByEnvironment, setActiveSessionIdByEnvironment] = useState<Record<RuntimeEnvironment, string | null>>(() => ({
    draft: projectId && agentId ? getStoredPlaygroundSessionId(projectId, agentId, 'draft') : null,
    staging: projectId && agentId ? getStoredPlaygroundSessionId(projectId, agentId, 'staging') : null,
    production: projectId && agentId ? getStoredPlaygroundSessionId(projectId, agentId, 'production') : null,
  }))
  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null)
  const [lastRequestPayload, setLastRequestPayload] = useState<Record<string, unknown> | null>(null)
  const [rawEvents, setRawEvents] = useState<RawStreamEvent[]>([])
  const rawEventsRef = useRef<RawStreamEvent[]>([])
  const [leftPanelTab, setLeftPanelTab] = useState<LeftPanelTab | null>('debug')
  const [showLeftPanel, setShowLeftPanel] = useState(false)
  const [showRightPanel, setShowRightPanel] = useState(true)
  const [rightPanelTab, setRightPanelTab] = useState('editor')
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [showApiModal, setShowApiModal] = useState(false)
  const [externalContextValues, setExternalContextValues] = useState<Record<string, unknown>>({})
  const externalContextOwnerRef = useRef<string | null>(null)
  const externalContextDirtyRef = useRef(false)
  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})
  const syncedSessionRef = useRef<string | null>(null)
  const currentRunIdRef = useRef<string | null>(null)
  const reattachingRunRef = useRef<string | null>(null)
  const mountedRef = useRef(true)

  const sessionIdState = activeSessionIdByEnvironment[environment]
  const environmentRelease = environment === 'draft' ? null : currentEnvironmentRelease
  const environmentReady = environment === 'draft' || Boolean(currentEnvironmentRelease)
  const runtimeEnabled = runtimeStatesQuery.data?.[environment]?.enabled ?? true
  const agentSessionMode: 'stateful' | 'stateless' = environment === 'draft'
    ? state.sessionMode === 'stateless' ? 'stateless' : 'stateful'
    : agent?.session_mode === 'stateless' ? 'stateless' : 'stateful'
  const isStateless = agentSessionMode === 'stateless'
  const sessionIdForRun = isStateless ? null : sessionIdState
  const selectedSessionId = sessionIdState
  useEffect(() => {
    const rememberedContext = projectId && agentId
      ? getStoredPlaygroundExternalContext(projectId, agentId, environment)
      : null
    const environmentValues = filterContractValues(
      activeExternalContextContract,
      rememberedContext ?? storedEnvironmentContext,
    )
    const ownerKey = `${projectId ?? ''}:${agentId ?? ''}:${environment}`
    const previousOwner = externalContextOwnerRef.current
    const contextDirty = externalContextDirtyRef.current

    setExternalContextValues((current) => {
      const currentValues = filterContractValues(activeExternalContextContract, current)
      if (previousOwner === null || previousOwner !== ownerKey) {
        return environmentValues
      }
      return contextDirty ? currentValues : environmentValues
    })

    if (previousOwner !== ownerKey) externalContextDirtyRef.current = false
    externalContextOwnerRef.current = ownerKey
  }, [
    activeExternalContextContract,
    agentId,
    environment,
    projectId,
    storedEnvironmentContext,
  ])

  const handleExternalContextValuesChange = useCallback((values: Record<string, unknown>) => {
    const filtered = filterContractValues(activeExternalContextContract, values)
    externalContextDirtyRef.current = true
    setExternalContextValues(filtered)
    if (projectId && agentId) {
      setStoredPlaygroundExternalContext(projectId, agentId, environment, filtered)
    }
  }, [activeExternalContextContract, agentId, environment, projectId])

  const handleClearExternalContextValues = useCallback(() => {
    externalContextDirtyRef.current = true
    setExternalContextValues({})
    if (projectId && agentId) {
      setStoredPlaygroundExternalContext(projectId, agentId, environment, {})
    }
  }, [agentId, environment, projectId])



  const {
    data: backendTraces = [],
    isLoading: tracesLoading,
    isError: tracesError,
    error: tracesQueryError,
    refetch: refetchTraces,
  } = usePlaygroundTraces(projectId, agentId, selectedSessionId, environment, isSending)

  const { data: historyMessages, isFetching } = useSessionMessages(selectedSessionId ?? undefined)
  const isSessionLoading = messages.length === 0
    && Boolean(selectedSessionId)
    && historyMessages === undefined
    && isFetching
    && syncedSessionRef.current !== selectedSessionId

  const setCurrentSessionId = useCallback((sessionId: string | null) => {
    setActiveSessionIdByEnvironment((current) => ({ ...current, [environment]: sessionId }))
    if (projectId && agentId) setStoredPlaygroundSessionId(projectId, agentId, environment, sessionId)
  }, [agentId, environment, projectId])

  const rememberRunId = useCallback((runId: string | null) => {
    currentRunIdRef.current = runId
    if (projectId && agentId) setStoredPlaygroundRunId(projectId, agentId, environment, runId)
  }, [agentId, environment, projectId])

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])
  useEffect(() => { setPlaygroundSessionId(selectedSessionId) }, [selectedSessionId])
  useEffect(() => {
    if (!isDirty) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isDirty])

  useEffect(() => {
    if (historyMessages && selectedSessionId && !isSending && !isFetching && syncedSessionRef.current !== selectedSessionId) {
      const mapped: ChatMessage[] = historyMessages.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        message_id: m.id,
        run_id: (m.data?.run_id as string | undefined) ?? null,
        phase: (m.data?.phase as string | undefined) ?? null,
        output_mode: m.data?.output_mode === 'intermediate' ? 'intermediate' : m.role === 'assistant' ? 'final' : null,
        partial: typeof m.data?.partial === 'boolean' ? m.data.partial : null,
        usage: m.input_tokens != null ? { input_tokens: m.input_tokens, output_tokens: m.output_tokens ?? null, cost_usd: null } : null,
        tool_calls: (m.data?.tool_calls ?? null) as ChatMessage['tool_calls'],
        sources: (m.data?.sources ?? null) as ChatMessage['sources'],
        model: (m.data?.model as string | undefined) ?? null,
        provider: (m.data?.provider as string | undefined) ?? null,
        output_parse_error: (m.data?.output_parse_error as string | undefined) ?? null,
      }))
      syncedSessionRef.current = selectedSessionId
      setMessages(mapped)
    }
  }, [historyMessages, selectedSessionId, isSending, isFetching])

  const resetConversationView = useCallback(() => {
    syncedSessionRef.current = null
    setMessages([])
    setLastResponse(null)
    setLastRequestPayload(null)
    setRawEvents([])
    rawEventsRef.current = []
    setSelectedTraceId(null)
  }, [])

  const handleEnvironmentChange = useCallback((next: RuntimeEnvironment) => {
    if (next === environment || isSending) return
    disconnectStream()
    resetConversationView()
    setEnvironment(next)
  }, [disconnectStream, environment, isSending, resetConversationView])

  const handleSessionSelect = useCallback((sessionIdValue: string) => {
    disconnectStream()
    resetConversationView()
    setCurrentSessionId(sessionIdValue)
    queryClient.invalidateQueries({ queryKey: ['session-messages', sessionIdValue] })
  }, [disconnectStream, queryClient, resetConversationView, setCurrentSessionId])

  const handleNewSession = useCallback(async () => {
    if (!projectId || !agentId || creatingSession) return
    if (!environmentReady) {
      toast.info(`Create the ${environment} version before starting its Chat`)
      return
    }
    if (!runtimeEnabled) {
      toast.error(`${titleCaseEnvironment(environment)} runtime is off`)
      return
    }
    if (isStateless) {
      toast.info('The Agent runtime is stateless and does not create persistent Sessions')
      return
    }
    disconnectStream()
    const sessionData: Record<string, unknown> = {
      source: 'playground',
      client_created_at: new Date().toISOString(),
    }

    try {
      const created = await createRuntimeSession({
        project_id: projectId,
        agent_id: agentId,
        runtime_environment: environment,
        data: sessionData,
      })
      const listItem: SessionListItem = {
        id: created.id,
        project_id: created.project_id,
        agent_id: created.agent_id,
        runtime_environment: created.runtime_environment,
        opened_release_id: created.opened_release_id ?? null,
        opened_release_version: created.opened_release_id ? releaseVersionById.get(created.opened_release_id) ?? null : null,
        status: created.status,
        mode: created.mode ?? 'chat',
        data: created.data ?? sessionData,
        last_message_at: created.last_message_at ?? null,
        created_at: created.created_at ?? null,
        message_count: 0,
      }
      queryClient.setQueryData<InfiniteData<SessionListPage>>(['agent-sessions', agentId, projectId, environment], (old) => {
        const newPage: SessionListPage = { items: [listItem], next_cursor: null, has_next: false }
        if (!old || old.pages.length === 0) return { pages: [newPage], pageParams: [null] }
        const [firstPage, ...restPages] = old.pages
        return {
          ...old,
          pages: [
            { ...firstPage, items: [listItem, ...firstPage.items.filter((item) => item.id !== listItem.id)] },
            ...restPages.map((page) => ({ ...page, items: page.items.filter((item) => item.id !== listItem.id) })),
          ],
        }
      })
      syncedSessionRef.current = created.id
      setCurrentSessionId(created.id)
      setMessages([])
      setLastResponse(null)
      setRawEvents([])
      rawEventsRef.current = []
      setSelectedTraceId(null)
      setIsSending(false)
      queryClient.invalidateQueries({ queryKey: ['session-messages', created.id] })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not create Session')
    }
  }, [agentId, createRuntimeSession, creatingSession, disconnectStream, environment, environmentReady, isStateless, projectId, queryClient, releaseVersionById, runtimeEnabled, setCurrentSessionId])

  const updateLastAssistantMessage = useCallback((updater: (message: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last?.role === 'assistant') updated[updated.length - 1] = updater(last)
      return updated
    })
  }, [])

  const upsertIntermediateAssistantMessage = useCallback((
    info: AssistantMessageInfo,
    append: boolean,
  ) => {
    setMessages((prev) => {
      const existingIndex = prev.findIndex((message) => (
        message.role === 'assistant' && message.message_id === info.message_id
      ))
      if (existingIndex >= 0) {
        const updated = [...prev]
        const existing = updated[existingIndex]
        updated[existingIndex] = {
          ...existing,
          content: append ? existing.content + info.content : info.content,
          phase: info.phase ?? existing.phase ?? null,
          output_mode: 'intermediate',
          partial: info.partial ?? existing.partial ?? null,
          model: info.model ?? existing.model ?? null,
          provider: info.provider ?? existing.provider ?? null,
          activity: null,
        }
        return updated
      }

      const message: ChatMessage = {
        role: 'assistant',
        content: info.content,
        message_id: info.message_id,
        run_id: currentRunIdRef.current,
        phase: info.phase ?? null,
        output_mode: 'intermediate',
        partial: info.partial ?? null,
        model: info.model ?? null,
        provider: info.provider ?? null,
        activity: null,
      }
      const last = prev[prev.length - 1]
      if (last?.role === 'assistant' && last.output_mode !== 'intermediate') {
        return [...prev.slice(0, -1), message, last]
      }
      return [...prev, message]
    })
  }, [])

  const reconcileCancelledAssistant = useCallback((event: Record<string, unknown>) => {
    const output = typeof event.output === 'string' ? event.output : accumulatedRef.current
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last?.role !== 'assistant') return prev
      const finalContent = output || last.content || ''
      if (!finalContent.trim() && !last.tool_calls?.length && !last.sources?.length) {
        return prev.slice(0, -1)
      }
      const updated = [...prev]
      updated[updated.length - 1] = { ...last, content: finalContent, activity: null }
      return updated
    })
  }, [])

  useEffect(() => {
    if (!projectId || !agentId || isSending || isFetching) return
    if (!isStateless && (!selectedSessionId || syncedSessionRef.current !== selectedSessionId)) return

    let disposed = false
    void (async () => {
      let runId = getStoredPlaygroundRunId(projectId, agentId, environment)
      if (!runId && selectedSessionId) {
        try {
          runId = (await getActiveAgentRun(selectedSessionId))?.run_id ?? null
        } catch {
          return
        }
      }
      if (!runId || disposed || reattachingRunRef.current === runId) return

      reattachingRunRef.current = runId
      rememberRunId(runId)
      accumulatedRef.current = ''
      metadataRef.current = {}
      rawEventsRef.current = []
      setMessages((current) => {
        const last = current[current.length - 1]
        if (last?.role === 'assistant' && last.output_mode !== 'intermediate') return current
        return [...current, { role: 'assistant', content: '', output_mode: 'final', activity: { status: 'working', message: 'Reattaching to active Run...' } }]
      })
      setIsSending(true)

      try {
        await reattach(runId, {
          onMeta: (meta) => {
            rawEventsRef.current.push({ type: 'meta', timestamp: new Date().toISOString(), payload: meta })
            if (meta.run_id) rememberRunId(meta.run_id)
            if (!isStateless && meta.session_id) setCurrentSessionId(meta.session_id)
            if (meta.trace_id) metadataRef.current.trace_id = meta.trace_id
          },
          onAgentActivity: (activity) => {
            rawEventsRef.current.push({ type: 'agent_activity', timestamp: new Date().toISOString(), payload: activity })
            updateLastAssistantMessage((last) => ({ ...last, activity }))
          },
          onAssistantMessageDelta: (info) => {
            rawEventsRef.current.push({ type: 'assistant_message_delta', timestamp: new Date().toISOString(), payload: info })
            upsertIntermediateAssistantMessage(info, true)
          },
          onAssistantMessageCompleted: (info) => {
            rawEventsRef.current.push({ type: 'assistant_message_completed', timestamp: new Date().toISOString(), payload: info })
            upsertIntermediateAssistantMessage(info, false)
          },
          onToken: (token) => {
            rawEventsRef.current.push({ type: 'token', timestamp: new Date().toISOString(), payload: token })
            if (token.visibility !== 'assistant' || token.channel !== 'final') return
            accumulatedRef.current += token.content
            updateLastAssistantMessage((last) => ({
              ...last,
              content: accumulatedRef.current,
              message_id: token.message_id ?? last.message_id ?? null,
              phase: token.phase ?? last.phase ?? null,
              output_mode: 'final',
              activity: null,
            }))
          },
          onTokenRetract: (info) => {
            rawEventsRef.current.push({ type: 'token_retract', timestamp: new Date().toISOString(), payload: info })
            if (info.content_length > 0) accumulatedRef.current = accumulatedRef.current.slice(0, Math.max(0, accumulatedRef.current.length - info.content_length))
            updateLastAssistantMessage((last) => ({ ...last, content: accumulatedRef.current }))
          },
          onInternalToken: (token) => rawEventsRef.current.push({ type: 'internal_token', timestamp: new Date().toISOString(), payload: token }),
          onSources: (sources) => {
            metadataRef.current.sources = sources
            rawEventsRef.current.push({ type: 'sources', timestamp: new Date().toISOString(), payload: { sources } })
          },
          onToolCallStarted: (info) => {
            const runningInfo: ToolCallInfo = { ...info, status: info.status ?? 'running' }
            updateLastAssistantMessage((last) => ({ ...last, tool_calls: upsertToolCall(last.tool_calls, runningInfo) }))
          },
          onToolCallCompleted: (info) => {
            updateLastAssistantMessage((last) => ({ ...last, tool_calls: upsertToolCall(last.tool_calls, info) }))
          },
          onDone: (response) => {
            const finalContent = response.answer || accumulatedRef.current || ''
            updateLastAssistantMessage((last) => ({
              ...last,
              content: finalContent,
              message_id: response.message_id ?? last.message_id ?? null,
              output_mode: 'final',
              activity: null,
              usage: response.usage ?? null,
              sources: (response.sources ?? metadataRef.current.sources) as ChatMessage['sources'],
              tool_calls: (response.tool_calls ?? last.tool_calls ?? null) as ChatMessage['tool_calls'],
              model: response.model ?? null,
              provider: response.provider ?? null,
              latency_ms: response.latency_ms ?? null,
              trace_id: response.trace_id ?? metadataRef.current.trace_id ?? null,
              parsed_output: response.parsed_output ?? null,
              output_parse_error: response.output_parse_error ?? null,
            }))
            setRawEvents([...rawEventsRef.current])
            setLastResponse(response as AskResponse)
            rememberRunId(null)
          },
          onError: (error) => {
            rememberRunId(null)
            setRawEvents([...rawEventsRef.current])
            updateLastAssistantMessage((last) => ({ ...last, activity: null, output_parse_error: error.message }))
            toast.error(error.message)
          },
          onCancelled: (event) => {
            rawEventsRef.current.push({ type: 'cancelled', timestamp: new Date().toISOString(), payload: event })
            setRawEvents([...rawEventsRef.current])
            reconcileCancelledAssistant(event)
            rememberRunId(null)
            toast.info('Agent Run cancelled')
          },
          onFallback: (info) => {
            accumulatedRef.current = ''
            updateLastAssistantMessage((last) => ({ ...last, content: '', activity: { status: 'working', message: `Trying ${info.fallback_provider}/${info.fallback_model}...` } }))
          },
        })
      } catch (error) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          // Keep the Run id after transport failure. A later reload/reattach can recover it.
          toast.warning(error instanceof Error ? error.message : 'Active Run reattach failed')
        }
      } finally {
        if (reattachingRunRef.current === runId) {
          reattachingRunRef.current = null
        }
        if (mountedRef.current) setIsSending(false)
      }
    })()

    return () => { disposed = true }
  }, [agentId, environment, isFetching, isSending, isStateless, projectId, reattach, reconcileCancelledAssistant, rememberRunId, selectedSessionId, setCurrentSessionId, updateLastAssistantMessage, upsertIntermediateAssistantMessage])

  const handleStop = useCallback(() => {
    cancelStream({
      onDispatched: () => toast.info('Agent Run cancellation requested'),
      onError: (_runId, error) => toast.warning(error.message),
    })
  }, [cancelStream])

  const handleSend = async (content: string) => {
    if (isSending || !agent) return
    if (!environmentReady) {
      toast.info(`Create the ${environment} version before starting its Chat`)
      return
    }
    if (!runtimeEnabled) {
      toast.error(`${titleCaseEnvironment(environment)} runtime is off`)
      return
    }

    let draftSnapshot: Record<string, unknown> | null = null
    if (environment === 'draft') {
      const validation = validateAgentEditorState(state)
      if (!validation.valid) {
        setEditorSection(validation.issue.section)
        setRightPanelTab('editor')
        setShowRightPanel(true)
        toast.error(validation.issue.message)
        return
      }
      draftSnapshot = validation.snapshot
    }

    accumulatedRef.current = ''
    metadataRef.current = {}
    rawEventsRef.current = []
    setMessages((prev) => [...prev, { role: 'user', content }, { role: 'assistant', content: '', output_mode: 'final', activity: { status: 'working', message: 'Working...' } }])
    setIsSending(true)

    try {
      const requestPayload: AskRequest = {
        project_id: projectId!,
        agent_id: agentId!,
        message: content,
        session_id: sessionIdForRun,
        execution_context: environment === 'draft' ? 'playground' : environment,
        external_context: externalContextValues,
        metadata: {
          source: 'playground',
          runtime_environment: environment,
          client_sent_at: new Date().toISOString(),
        },
        ...(draftSnapshot ? { snapshot_override: draftSnapshot } : {}),
      }
      setLastRequestPayload(requestPayload as unknown as Record<string, unknown>)
      await stream(requestPayload, {
        onMeta: (meta) => {
          rawEventsRef.current.push({ type: 'meta', timestamp: new Date().toISOString(), payload: meta })
          if (meta.run_id) rememberRunId(meta.run_id)
          if (!isStateless && meta.session_id) setCurrentSessionId(meta.session_id)
          if (meta.trace_id) metadataRef.current.trace_id = meta.trace_id
        },
        onAgentActivity: (activity) => {
          rawEventsRef.current.push({ type: 'agent_activity', timestamp: new Date().toISOString(), payload: activity })
          updateLastAssistantMessage((last) => ({ ...last, activity }))
        },
        onAssistantMessageDelta: (info) => {
          rawEventsRef.current.push({ type: 'assistant_message_delta', timestamp: new Date().toISOString(), payload: info })
          upsertIntermediateAssistantMessage(info, true)
        },
        onAssistantMessageCompleted: (info) => {
          rawEventsRef.current.push({ type: 'assistant_message_completed', timestamp: new Date().toISOString(), payload: info })
          upsertIntermediateAssistantMessage(info, false)
        },
        onToken: (token) => {
          rawEventsRef.current.push({ type: 'token', timestamp: new Date().toISOString(), payload: token })
          if (token.visibility !== 'assistant' || token.channel !== 'final') return
          accumulatedRef.current += token.content
          updateLastAssistantMessage((last) => ({
            ...last,
            content: accumulatedRef.current,
            message_id: token.message_id ?? last.message_id ?? null,
            phase: token.phase ?? last.phase ?? null,
            output_mode: 'final',
            activity: null,
          }))
        },
        onTokenRetract: (info) => {
          rawEventsRef.current.push({ type: 'token_retract', timestamp: new Date().toISOString(), payload: info })
          if (info.content_length > 0) accumulatedRef.current = accumulatedRef.current.slice(0, Math.max(0, accumulatedRef.current.length - info.content_length))
          updateLastAssistantMessage((last) => ({ ...last, activity: { status: 'planning_tools', message: 'Checking whether tools are needed...' } }))
        },
        onInternalToken: (token) => rawEventsRef.current.push({ type: 'internal_token', timestamp: new Date().toISOString(), payload: token }),
        onSources: (sources) => {
          rawEventsRef.current.push({ type: 'sources', timestamp: new Date().toISOString(), payload: { sources } })
          metadataRef.current.sources = sources
        },
        onToolCallStarted: (info) => {
          const runningInfo: ToolCallInfo = { ...info, status: info.status ?? 'running' }
          rawEventsRef.current.push({ type: 'tool_call_started', timestamp: new Date().toISOString(), payload: runningInfo })
          updateLastAssistantMessage((last) => ({ ...last, activity: { status: 'calling_tool', message: `Calling tool: ${runningInfo.tool_name}...`, tool_name: runningInfo.tool_name }, tool_calls: upsertToolCall(last.tool_calls, runningInfo) }))
        },
        onToolCallCompleted: (info) => {
          rawEventsRef.current.push({ type: 'tool_call_completed', timestamp: new Date().toISOString(), payload: info })
          updateLastAssistantMessage((last) => ({ ...last, activity: { status: 'processing_tool_result', message: 'Processing tool result...', tool_name: info.tool_name }, tool_calls: upsertToolCall(last.tool_calls, info) }))
        },
        onDone: (response) => {
          for (const event of response.execution_events ?? []) rawEventsRef.current.push({ type: event.event_type, timestamp: event.occurred_at, payload: event })
          rawEventsRef.current.push({ type: 'done', timestamp: new Date().toISOString(), payload: response })
          setRawEvents([...rawEventsRef.current])
          const meta = response
          const finalContent = meta.answer || accumulatedRef.current || ''
          if (!isStateless && meta.session_id) setCurrentSessionId(meta.session_id)
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.role === 'assistant') updated[updated.length - 1] = { ...last, content: finalContent, message_id: meta.message_id ?? last.message_id ?? null, output_mode: 'final', activity: null, usage: meta.usage ?? null, sources: (meta.sources ?? metadataRef.current.sources) as ChatMessage['sources'], tool_calls: (meta.tool_calls ?? last.tool_calls ?? null) as ChatMessage['tool_calls'], model: meta.model ?? null, provider: meta.provider ?? null, latency_ms: meta.latency_ms ?? null, trace_id: meta.trace_id ?? null, parsed_output: meta.parsed_output ?? null, output_parse_error: meta.output_parse_error ?? null }
            return updated
          })
          setLastResponse(meta as AskResponse)
          rememberRunId(null)
          if (!isStateless) void refetchSessions()
          if (!isStateless && meta.session_id) syncedSessionRef.current = meta.session_id
          if (meta.trace_id) setTimeout(() => setSelectedTraceId(meta.trace_id!), 100)
        },
        onError: (error) => {
          rawEventsRef.current.push({ type: 'error', timestamp: new Date().toISOString(), payload: { message: error.message } })
          setRawEvents([...rawEventsRef.current])
          rememberRunId(null)
          toast.error(error.message)
          updateLastAssistantMessage((last) => ({ ...last, activity: null, content: last.content || `Error: ${error.message}`, output_parse_error: error.message, trace_id: metadataRef.current.trace_id ?? null }))
        },
        onCancelled: (event) => {
          rawEventsRef.current.push({ type: 'cancelled', timestamp: new Date().toISOString(), payload: event })
          setRawEvents([...rawEventsRef.current])
          reconcileCancelledAssistant(event)
          rememberRunId(null)
          toast.info('Agent Run cancelled')
          if (metadataRef.current.trace_id) setTimeout(() => setSelectedTraceId(metadataRef.current.trace_id!), 100)
        },
        onFallback: (info) => {
          rawEventsRef.current.push({ type: 'fallback', timestamp: new Date().toISOString(), payload: info })
          accumulatedRef.current = ''
          updateLastAssistantMessage((last) => ({ ...last, content: '', activity: { status: 'working', message: 'Trying fallback model...' } }))
          toast.info(`Primary model (${info.primary_provider}/${info.primary_model}) failed. Retrying with ${info.fallback_provider}/${info.fallback_model}...`)
        },
      })
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      toast.error(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setIsSending(false)
    }
  }

  const handleLeftPanelTabChange = (tab: LeftPanelTab) => {
    if (leftPanelTab === tab) setShowLeftPanel(!showLeftPanel)
    else { setLeftPanelTab(tab); setShowLeftPanel(true); setSelectedTraceId(null) }
  }

  const handleLoadMoreSessions = useCallback(() => {
    if (!hasMoreSessions || sessionsLoadingMore) return
    void fetchNextSessionsPage()
  }, [fetchNextSessionsPage, hasMoreSessions, sessionsLoadingMore])

  const traces = useMemo(() => {
    const mapped: TraceItem[] = backendTraces
      .filter((trace) => traceEnvironment((trace.data ?? {}) as Record<string, unknown>) === environment)
      .map((t) => {
        const traceData = (t.data ?? {}) as Record<string, unknown>
        const mapStatus = (s: string): TraceItem['status'] => {
          if (s === 'completed' || s === 'success') return 'success'
          if (s === 'failed' || s === 'error' || s === 'timed_out' || s === 'timeout') return 'error'
          if (s === 'running' || s === 'processing') return 'running'
          if (s === 'pending' || s === 'queued') return 'pending'
          if (s === 'cancelled' || s === 'canceled') return 'cancelled'
          return 'warning'
        }
        return { id: t.id, run_id: typeof traceData.agent_run_id === 'string' ? traceData.agent_run_id : null, title: t.status === 'failed' ? `Failed (${t.error?.slice(0, 40) || 'error'})` : `Agent Run ${t.status}`, timestamp: t.created_at ?? new Date().toISOString(), status: mapStatus(t.status), latency_ms: t.total_latency_ms ?? null, model: t.model ?? null, provider: t.provider ?? null, input_tokens: (traceData.input_tokens as number) ?? null, output_tokens: (traceData.output_tokens as number) ?? null, total_tokens: (traceData.total_tokens as number) ?? null, cost_usd: (traceData.cost_usd as number) ?? t.total_cost_usd ?? null, trace_id: t.id, response: null, project_id: t.project_id, agent_id: t.agent_id }
      })
    mapped.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    return mapped
  }, [backendTraces, environment])

  if (agentLoading) return <AgentPlaygroundSkeleton />
  if (agentError) return <ErrorState message="Failed to load Agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  const environmentLabel = titleCaseEnvironment(environment)
  const versionLabel = environment === 'draft'
    ? isDirty ? 'Draft (unsaved)' : 'Current Draft'
    : currentEnvironmentRelease?.version ?? 'not created'
  const statusLabel = `Using: ${environment === 'draft' ? versionLabel : `${environmentLabel} · ${versionLabel}`}`
  const runtimeBlockReason = !environmentReady
    ? environment === 'staging'
      ? 'Staging has not been created. Create an immutable Staging snapshot before testing it.'
      : 'Production has not been deployed. Activate an Agent Release before testing Production.'
    : runtimeEnabled
      ? undefined
      : `${environmentLabel} runtime is off. Configuration and release management remain available.`
  const sessionCreationDisabledReason = !environmentReady
    ? `${environmentLabel} has not been created yet.`
    : !runtimeEnabled
      ? `${environmentLabel} runtime is off.`
      : isStateless
        ? 'This Agent runtime is stateless.'
        : undefined
  const visibleProvider = environment === 'draft' ? state.provider : currentEnvironmentRelease?.provider
  const visibleModel = environment === 'draft' ? state.model : currentEnvironmentRelease?.model

  return (
    <ErrorBoundary>
      <div className="-m-6 h-[calc(100vh-3.5rem)] overflow-hidden flex flex-col bg-background">
        <PlaygroundHeader
          agent={agent}
          projectId={projectId!}
          showLeftPanel={showLeftPanel}
          showRightPanel={showRightPanel}
          environment={environment}
          environmentChangeDisabled={isSending}
          onEnvironmentChange={handleEnvironmentChange}
          onToggleLeftPanel={() => setShowLeftPanel(!showLeftPanel)}
          onToggleRightPanel={() => setShowRightPanel(!showRightPanel)}
          onApiClick={() => setShowApiModal(true)}
          onSettingsClick={() => navigate(p(projectId!, 'agents', agentId!, 'edit'))}
          releaseVersion={productionRelease?.version}
          releaseStatus={productionRelease?.status}
        />
        <div className="h-6 shrink-0 flex items-center px-4 border-b border-border text-[10px] bg-surface/30">
          <span className="text-muted font-medium">{statusLabel}</span>
          {environment === 'draft' && isDirty && <span className="ml-2 text-yellow-400 font-medium">· unsaved changes</span>}
          {!runtimeEnabled && <span className="ml-2 text-red-400 font-medium">· {environmentLabel} runtime off</span>}
          {!environmentReady && <span className="ml-2 text-amber-300 font-medium">· environment not created</span>}
          <span className="ml-auto text-muted">{visibleProvider || '—'}/{visibleModel || '—'}</span>
        </div>
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <OperationsRail
            activeTab={showLeftPanel ? leftPanelTab : null}
            environment={environment}
            onTabChange={handleLeftPanelTabChange}
            onNewSession={async () => {
              setShowLeftPanel(false)
              await handleNewSession()
            }}
            newSessionDisabled={isSending || Boolean(sessionCreationDisabledReason)}
            newSessionDisabledReason={isSending ? 'Wait for the active Agent Run to finish or stop it before creating a Session' : sessionCreationDisabledReason}
            newSessionPending={creatingSession}
          />
          {showLeftPanel && (
            <OperationsPanel
              activeTab={leftPanelTab}
              lastResponse={lastResponse}
              lastRequestPayload={lastRequestPayload}
              rawEvents={rawEvents}
              traces={traces}
              selectedTraceId={selectedTraceId}
              sessions={sessions}
              sessionId={selectedSessionId}
              sessionMode={agentSessionMode}
              onSelectTrace={setSelectedTraceId}
              onSelectSession={handleSessionSelect}
              onLoadMoreSessions={handleLoadMoreSessions}
              hasMoreSessions={Boolean(hasMoreSessions)}
              sessionsLoading={sessionsLoading || sessionsFetching}
              sessionsLoadingMore={sessionsLoadingMore}
              sessionsError={sessionsError}
              sessionsErrorMessage={sessionsQueryError instanceof Error ? sessionsQueryError.message : undefined}
              onSessionsRetry={() => { void refetchSessions() }}
              tracesLoading={tracesLoading}
              tracesError={tracesError}
              tracesErrorMessage={tracesQueryError instanceof Error ? tracesQueryError.message : undefined}
              onTracesRetry={refetchTraces}
            />
          )}
          <div className="flex-1 min-w-0 flex flex-col">
            <ChatCanvas
              messages={messages}
              isSending={isSending}
              isSessionLoading={isSessionLoading}
              onSend={handleSend}
              onStop={handleStop}
              agentName={agent.name}
              runtimeBlocked={!runtimeEnabled || !environmentReady}
              runtimeBlockReason={runtimeBlockReason}
              externalContextContract={activeExternalContextContract}
              externalContextValues={externalContextValues}
              onExternalContextValuesChange={handleExternalContextValuesChange}
              onClearExternalContextValues={handleClearExternalContextValues}
            />
          </div>
          {showRightPanel && <AgentInspector agent={agent} projectId={projectId!} agentId={agentId!} activeTab={rightPanelTab} environment={environment} environmentRelease={environmentRelease} environmentReleaseLoading={releasesLoading} onTabChange={setRightPanelTab} onCollapse={() => setShowRightPanel(false)} />}
        </div>
      </div>
      <ApiModal open={showApiModal} onClose={() => setShowApiModal(false)} agent={agent} projectId={projectId!} workspaceProjectPathFn={(projId, ...segments) => p(projId, ...segments)} />
    </ErrorBoundary>
  )
}

export default function AgentPlaygroundPage() {
  const { projectId, agentId } = useParams<{ workspaceId?: string; projectId: string; agentId: string }>()
  const { data: agent, isLoading } = useAgent(agentId)
  if (isLoading) return <AgentPlaygroundSkeleton />
  if (!agent) return <ErrorState message="Agent not found" />
  return <AgentEditorProvider agent={agent} projectId={projectId}><PlaygroundContent /></AgentEditorProvider>
}
