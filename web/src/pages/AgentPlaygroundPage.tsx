import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent, useReleases } from '@/features/agents/hooks'
import { usePlaygroundTraces } from '@/features/traces/hooks'
import { useAskStream, useAgentSessions, useCreateSession, useSessionMessages } from '@/features/playground/hooks'
import { ErrorState } from '@/components/common/ErrorState'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { orgProjectPath } from '@/lib/constants/routes'
import { PlaygroundHeader } from '@/features/playground/components/PlaygroundHeader'
import { OperationsRail, type LeftPanelTab } from '@/features/playground/components/OperationsRail'
import { OperationsPanel } from '@/features/playground/components/OperationsPanel'
import { ChatCanvas } from '@/features/playground/components/ChatCanvas'
import { AgentInspector } from '@/features/playground/components/AgentInspector'
import { ApiModal } from '@/features/playground/components/ApiModal'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { setPlaygroundSessionId } from '@/features/playground/lib/playground-session-store'
import { useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { AskResponse, ChatMessage, TraceItem, RawStreamEvent, ToolCallInfo, SessionListItem, SessionListPage } from '@/features/playground/types'

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
          <div className="border-b border-border/90 px-3 py-3">
            <SkeletonLine className="h-3 w-20" />
          </div>
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

function normalizeSessionMode(value?: string): 'stateful' | 'stateless' {
  return value === 'stateless' ? 'stateless' : 'stateful'
}

function PlaygroundContent() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)
  const { data: releases = [] } = useReleases(agentId)
  const { state, toSnapshot, isDirty } = useAgentEditor()
  const { stream, cancel: cancelStream } = useAskStream()
  const queryClient = useQueryClient()
  const { mutateAsync: createRuntimeSession, isPending: creatingSession } = useCreateSession()

  const agentSessionMode = normalizeSessionMode(agent?.session_mode)
  const isStateless = agentSessionMode === 'stateless'
  const isAgentInactive = agent?.status === 'inactive'

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)
  const productionRelease = releases.find(r => r.status === 'production')

  const {
    data: sessionPages,
    refetch: refetchSessions,
    fetchNextPage: fetchNextSessionsPage,
    hasNextPage: hasMoreSessions,
    isLoading: sessionsLoading,
    isFetchingNextPage: sessionsLoadingMore,
  } = useAgentSessions(agentId, projectId)

  const sessions = useMemo(() => {
    const byId = new Map<string, SessionListItem>()
    for (const page of sessionPages?.pages ?? []) {
      for (const item of page.items) if (!byId.has(item.id)) byId.set(item.id, item)
    }
    return Array.from(byId.values())
  }, [sessionPages])

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionIdState, setSessionIdState] = useState<string | null>(null)
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
  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})
  const syncedSessionRef = useRef<string | null>(null)
  const activeSessionId = isStateless ? null : sessionIdState

  const {
    data: backendTraces = [],
    isLoading: tracesLoading,
    isError: tracesError,
    error: tracesQueryError,
    refetch: refetchTraces,
  } = usePlaygroundTraces(projectId, agentId, activeSessionId)

  const { data: historyMessages, isFetching } = useSessionMessages(activeSessionId ?? undefined)
  const isSessionLoading = messages.length === 0 && Boolean(activeSessionId) && isFetching && syncedSessionRef.current !== activeSessionId

  useEffect(() => {
    setPlaygroundSessionId(activeSessionId)
  }, [activeSessionId])

  useEffect(() => {
    if (!isStateless || !sessionIdState) return
    cancelStream()
    syncedSessionRef.current = null
    setSessionIdState(null)
    setMessages([])
    setLastResponse(null)
    setRawEvents([])
    rawEventsRef.current = []
    setSelectedTraceId(null)
  }, [isStateless, sessionIdState, cancelStream])

  useEffect(() => {
    if (historyMessages && activeSessionId && !isSending && !isFetching && syncedSessionRef.current !== activeSessionId) {
      const mapped: ChatMessage[] = historyMessages.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        usage: m.input_tokens != null ? { input_tokens: m.input_tokens, output_tokens: m.output_tokens ?? null, cost_usd: null } : null,
        tool_calls: (m.data?.tool_calls ?? null) as ChatMessage['tool_calls'],
        sources: (m.data?.sources ?? null) as ChatMessage['sources'],
        model: (m.data?.model as string | undefined) ?? null,
        provider: (m.data?.provider as string | undefined) ?? null,
        output_parse_error: (m.data?.output_parse_error as string | undefined) ?? null,
      }))
      syncedSessionRef.current = activeSessionId
      setMessages(mapped)
    }
  }, [historyMessages, activeSessionId, isSending, isFetching])

  const handleSessionSelect = useCallback((sessionIdValue: string) => {
    if (isStateless) return
    syncedSessionRef.current = null
    cancelStream()
    setSessionIdState(sessionIdValue)
    setMessages([])
    setLastResponse(null)
    setRawEvents([])
    setSelectedTraceId(null)
    queryClient.invalidateQueries({ queryKey: ['session-messages', sessionIdValue] })
  }, [cancelStream, isStateless, queryClient])

  const handleNewSession = useCallback(async () => {
    if (!projectId || !agentId || creatingSession) return
    if (isStateless) {
      toast.info('Stateless agents do not create persistent sessions')
      return
    }
    cancelStream()
    try {
      const created = await createRuntimeSession({ project_id: projectId, agent_id: agentId, data: { source: 'playground', client_created_at: new Date().toISOString() } })
      const listItem: SessionListItem = { id: created.id, project_id: created.project_id, agent_id: created.agent_id, status: created.status, mode: created.mode ?? 'chat', last_message_at: created.last_message_at ?? null, created_at: created.created_at ?? null, message_count: 0 }
      queryClient.setQueryData<InfiniteData<SessionListPage>>(['agent-sessions', agentId, projectId], (old) => {
        const newPage: SessionListPage = { items: [listItem], next_cursor: null, has_next: false }
        if (!old || old.pages.length === 0) return { pages: [newPage], pageParams: [null] }
        const [firstPage, ...restPages] = old.pages
        return { ...old, pages: [{ ...firstPage, items: [listItem, ...firstPage.items.filter((item) => item.id !== listItem.id)] }, ...restPages.map((page) => ({ ...page, items: page.items.filter((item) => item.id !== listItem.id) }))] }
      })
      syncedSessionRef.current = created.id
      setSessionIdState(created.id)
      setMessages([])
      setLastResponse(null)
      setRawEvents([])
      rawEventsRef.current = []
      setSelectedTraceId(null)
      setIsSending(false)
      queryClient.invalidateQueries({ queryKey: ['session-messages', created.id] })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not create session')
    }
  }, [agentId, cancelStream, createRuntimeSession, creatingSession, isStateless, projectId, queryClient])

  const updateLastAssistantMessage = useCallback((updater: (message: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last?.role === 'assistant') updated[updated.length - 1] = updater(last)
      return updated
    })
  }, [])

  const handleSend = async (content: string) => {
    if (isSending || !agent) return
    if (isAgentInactive) {
      toast.error('Agent is inactive')
      return
    }

    accumulatedRef.current = ''
    metadataRef.current = {}
    rawEventsRef.current = []
    setMessages((prev) => [...prev, { role: 'user', content }, { role: 'assistant', content: '', activity: { status: 'working', message: 'Working...' } }])
    setIsSending(true)

    try {
      const requestPayload: Record<string, unknown> = { project_id: projectId!, agent_id: agentId!, message: content, session_id: isStateless ? null : sessionIdState, execution_context: 'playground', metadata: { client_sent_at: new Date().toISOString() }, snapshot_override: toSnapshot() }
      setLastRequestPayload(requestPayload)
      await stream(requestPayload as any, {
        onMeta: (meta) => {
          rawEventsRef.current.push({ type: 'meta', timestamp: new Date().toISOString(), payload: meta })
          if (!isStateless && meta.session_id) setSessionIdState(meta.session_id)
          if (meta.trace_id) metadataRef.current.trace_id = meta.trace_id
        },
        onAgentActivity: (activity) => {
          rawEventsRef.current.push({ type: 'agent_activity', timestamp: new Date().toISOString(), payload: activity })
          updateLastAssistantMessage((last) => ({ ...last, activity }))
        },
        onToken: (token) => {
          rawEventsRef.current.push({ type: 'token', timestamp: new Date().toISOString(), payload: token })
          if (token.visibility !== 'assistant' || token.channel !== 'final') return
          accumulatedRef.current += token.content
          updateLastAssistantMessage((last) => ({ ...last, content: accumulatedRef.current, activity: null }))
        },
        onTokenRetract: (info) => {
          rawEventsRef.current.push({ type: 'token_retract', timestamp: new Date().toISOString(), payload: info })
          if (info.content_length > 0) accumulatedRef.current = accumulatedRef.current.slice(0, Math.max(0, accumulatedRef.current.length - info.content_length))
          updateLastAssistantMessage((last) => ({ ...last, content: accumulatedRef.current, activity: { status: 'planning_tools', message: 'Checking whether tools are needed...' } }))
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
          if (!isStateless && meta.session_id) setSessionIdState(meta.session_id)
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.role === 'assistant') updated[updated.length - 1] = { ...last, content: finalContent, activity: null, usage: meta.usage ?? null, sources: (meta.sources ?? metadataRef.current.sources) as ChatMessage['sources'], tool_calls: (meta.tool_calls ?? last.tool_calls ?? null) as ChatMessage['tool_calls'], model: meta.model ?? null, provider: meta.provider ?? null, latency_ms: meta.latency_ms ?? null, trace_id: meta.trace_id ?? null, parsed_output: meta.parsed_output ?? null, output_parse_error: meta.output_parse_error ?? null }
            return updated
          })
          setLastResponse(meta as AskResponse)
          if (!isStateless) refetchSessions()
          refetchTraces()
          if (!isStateless && meta.session_id) {
            queryClient.invalidateQueries({ queryKey: ['session-messages', meta.session_id] })
            syncedSessionRef.current = meta.session_id
          }
          if (meta.trace_id) setTimeout(() => setSelectedTraceId(meta.trace_id!), 100)
        },
        onError: (error) => {
          rawEventsRef.current.push({ type: 'error', timestamp: new Date().toISOString(), payload: { message: error.message } })
          setRawEvents([...rawEventsRef.current])
          toast.error(error.message)
          updateLastAssistantMessage((last) => ({ ...last, activity: null, content: last.content || `Error: ${error.message}`, output_parse_error: error.message, trace_id: metadataRef.current.trace_id ?? null }))
          refetchTraces()
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
    const mapped: TraceItem[] = backendTraces.map((t) => {
      const traceData = (t.data ?? {}) as Record<string, unknown>
      const mapStatus = (s: string): TraceItem['status'] => {
        if (s === 'completed' || s === 'success') return 'success'
        if (s === 'failed' || s === 'error') return 'error'
        if (s === 'running' || s === 'processing') return 'running'
        if (s === 'pending' || s === 'queued') return 'pending'
        if (s === 'cancelled' || s === 'canceled') return 'cancelled'
        return 'warning'
      }
      return { id: t.id, title: t.status === 'failed' ? `Failed (${t.error?.slice(0, 40) || 'error'})` : `Trace ${t.status}`, timestamp: t.created_at ?? new Date().toISOString(), status: mapStatus(t.status), latency_ms: t.total_latency_ms ?? null, model: t.model ?? null, provider: t.provider ?? null, input_tokens: (traceData.input_tokens as number) ?? null, output_tokens: (traceData.output_tokens as number) ?? null, total_tokens: (traceData.total_tokens as number) ?? null, cost_usd: (traceData.cost_usd as number) ?? t.total_cost_usd ?? null, trace_id: t.id, response: null, project_id: t.project_id, agent_id: t.agent_id }
    })
    mapped.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    return mapped
  }, [backendTraces])

  if (agentLoading) return <AgentPlaygroundSkeleton />
  if (agentError) return <ErrorState message="Failed to load agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  const statusLabel = isDirty ? 'Using: Draft (unsaved)' : 'Using: Current Draft'
  const runtimeBlockReason = isAgentInactive ? 'Agent is inactive. Activate it in Runtime to run tests.' : undefined

  return (
    <ErrorBoundary>
      <div className="-m-6 h-[calc(100vh-3.5rem)] overflow-hidden flex flex-col bg-background">
        <PlaygroundHeader agent={agent} showLeftPanel={showLeftPanel} showRightPanel={showRightPanel} onToggleLeftPanel={() => setShowLeftPanel(!showLeftPanel)} onToggleRightPanel={() => setShowRightPanel(!showRightPanel)} onApiClick={() => setShowApiModal(true)} onSettingsClick={() => navigate(p(projectId!, 'agents', agentId!, 'edit'))} releaseVersion={productionRelease?.version} releaseStatus={productionRelease?.status} />
        <div className="h-6 shrink-0 flex items-center px-4 border-b border-border text-[10px] bg-surface/30"><span className="text-muted font-medium">{statusLabel}</span>{isDirty && <span className="ml-2 text-yellow-400 font-medium">· unsaved changes</span>}<span className="ml-2 text-muted">· {agentSessionMode}</span>{isAgentInactive && <span className="ml-2 text-red-400 font-medium">· inactive</span>}<span className="ml-auto text-muted">{state.provider}/{state.model}</span></div>
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <OperationsRail activeTab={showLeftPanel ? leftPanelTab : null} onTabChange={handleLeftPanelTabChange} />
          {showLeftPanel && <OperationsPanel activeTab={leftPanelTab} lastResponse={lastResponse} lastRequestPayload={lastRequestPayload} rawEvents={rawEvents} traces={traces} selectedTraceId={selectedTraceId} sessions={sessions} sessionId={activeSessionId} sessionMode={agentSessionMode} onSelectTrace={setSelectedTraceId} onNewSession={handleNewSession} onSelectSession={handleSessionSelect} onLoadMoreSessions={handleLoadMoreSessions} hasMoreSessions={Boolean(hasMoreSessions)} sessionsLoading={sessionsLoading} sessionsLoadingMore={sessionsLoadingMore} creatingSession={creatingSession} tracesLoading={tracesLoading} tracesError={tracesError} tracesErrorMessage={tracesQueryError instanceof Error ? tracesQueryError.message : undefined} onTracesRetry={refetchTraces} />}
          <div className="flex-1 min-w-0 flex flex-col"><ChatCanvas messages={messages} isSending={isSending} isSessionLoading={isSessionLoading} onSend={handleSend} agentName={agent?.name} runtimeBlocked={isAgentInactive} runtimeBlockReason={runtimeBlockReason} /></div>
          {showRightPanel && <AgentInspector agent={agent} projectId={projectId!} agentId={agentId!} activeTab={rightPanelTab} onTabChange={setRightPanelTab} onCollapse={() => setShowRightPanel(false)} />}
        </div>
      </div>
      <ApiModal open={showApiModal} onClose={() => setShowApiModal(false)} agent={agent} projectId={projectId!} orgProjectPathFn={(projId, ...segments) => p(projId, ...segments)} />
    </ErrorBoundary>
  )
}

export default function AgentPlaygroundPage() {
  const { projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const { data: agent, isLoading } = useAgent(agentId)
  if (isLoading) return <AgentPlaygroundSkeleton />
  if (!agent) return <ErrorState message="Agent not found" />
  return <AgentEditorProvider agent={agent} projectId={projectId}><PlaygroundContent /></AgentEditorProvider>
}