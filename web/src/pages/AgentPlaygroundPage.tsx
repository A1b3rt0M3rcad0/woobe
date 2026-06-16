import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useAgent, useReleases } from '@/features/agents/hooks'
import { usePlaygroundTraces } from '@/features/traces/hooks'
import { useAskStream, useAgentSessions, useSessionMessages } from '@/features/playground/hooks'
import { LoadingState } from '@/components/common/LoadingState'
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
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { AskResponse, SessionListItem, ChatMessage, TraceItem, RawStreamEvent } from '@/features/playground/types'

function PlaygroundContent() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)
  const { data: releases = [] } = useReleases(agentId)

  const productionRelease = releases.find(r => r.status === 'production')
  const releaseVersion = productionRelease?.version
  const releaseStatus = productionRelease?.status

  const { state, toSnapshot, isDirty, activeSource } = useAgentEditor()

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)
  const { stream, cancel: cancelStream } = useAskStream()
  const queryClient = useQueryClient()

  const { data: sessions = [], refetch: refetchSessions } = useAgentSessions(agentId, projectId)

  const [messages, setMessages] = useState<ChatMessage[]>([])

  const urlSessionId = searchParams.get('session') || null
  const [sessionId, setSessionIdState] = useState<string | null>(urlSessionId)

  const setSessionId = useCallback((value: string | null) => {
    setSessionIdState(value)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) {
        next.set('session', value)
      } else {
        next.delete('session')
      }
      return next
    }, { replace: true })
  }, [setSearchParams])

  const prevAgentRef = useRef(agentId)
  useEffect(() => {
    if (prevAgentRef.current !== agentId) {
      prevAgentRef.current = agentId
      setSessionId(null)
    }
  }, [agentId, setSessionId])

  useEffect(() => {
    if (!sessionId || !sessions.length) return
    const belongs = sessions.some((s) => s.id === sessionId)
    if (!belongs) {
      setSessionId(null)
    }
  }, [sessionId, sessions, setSessionId])

  useEffect(() => {
    if (state.sessionMode === 'stateless' && sessionId) {
      setSessionId(null)
    }
  }, [state.sessionMode, sessionId, setSessionId])
  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null)
  const [lastRequestPayload, setLastRequestPayload] = useState<Record<string, unknown> | null>(null)
  const [rawEvents, setRawEvents] = useState<RawStreamEvent[]>([])
  const rawEventsRef = useRef<RawStreamEvent[]>([])

  const [leftPanelTab, setLeftPanelTab] = useState<LeftPanelTab | null>('debug')
  const [showLeftPanel, setShowLeftPanel] = useState(true)
  const [showRightPanel, setShowRightPanel] = useState(true)
  const [rightPanelTab, setRightPanelTab] = useState('editor')
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [showApiModal, setShowApiModal] = useState(false)

  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})
  const syncedSessionRef = useRef<string | null>(null)

  const {
    data: backendTraces = [],
    isLoading: tracesLoading,
    isError: tracesError,
    error: tracesQueryError,
    refetch: refetchTraces,
  } = usePlaygroundTraces(projectId, agentId, sessionId)

  const selectedSessionId = sessionId
  const { data: historyMessages, isFetching } = useSessionMessages(
    selectedSessionId ?? undefined,
  )

  useEffect(() => {
    if (historyMessages && selectedSessionId && !isSending && !isFetching && syncedSessionRef.current !== selectedSessionId) {
      const mapped: ChatMessage[] = historyMessages.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        usage: m.input_tokens != null ? { input_tokens: m.input_tokens, output_tokens: m.output_tokens ?? null, cost_usd: null } : null,
        tool_calls: (m.data?.tool_calls ?? null) as ChatMessage['tool_calls'],
        sources: (m.data?.sources ?? null) as ChatMessage['sources'],
        model: (m.data?.model as string | undefined) ?? null,
        provider: (m.data?.provider as string | undefined) ?? null,
      }))
      syncedSessionRef.current = selectedSessionId
      setMessages(mapped)
    }
  }, [historyMessages, selectedSessionId, isSending, isFetching])

  const handleSessionSelect = useCallback((sessionIdValue: string) => {
    syncedSessionRef.current = null
    cancelStream()
    setSessionId(sessionIdValue)
    setMessages([])
    setLastResponse(null)
    setRawEvents([])
    setSelectedTraceId(null)
    queryClient.invalidateQueries({ queryKey: ['session-messages', sessionIdValue] })
  }, [cancelStream, queryClient])

  const handleNewSession = useCallback(() => {
    syncedSessionRef.current = null
    cancelStream()
    setSessionId(null)
    setMessages([])
    setLastResponse(null)
    setRawEvents([])
    setSelectedTraceId(null)
  }, [cancelStream])

  const handleSend = async (content: string) => {
    if (isSending || !agent) return

    accumulatedRef.current = ''
    metadataRef.current = {}
    rawEventsRef.current = []

    const userMsg: ChatMessage = { role: 'user', content }
    const assistantMsg: ChatMessage = { role: 'assistant', content: '' }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsSending(true)

    try {
      const requestPayload: Record<string, unknown> = {
        project_id: projectId!,
        agent_id: agentId!,
        message: content,
        session_id: sessionId,
        execution_context: 'playground',
      }

      requestPayload.snapshot_override = toSnapshot()
      setLastRequestPayload(requestPayload)

      await stream(
        requestPayload as any,
        {
          onMeta: (meta) => {
            rawEventsRef.current.push({ type: 'meta', timestamp: new Date().toISOString(), payload: meta })
            if (meta.session_id) {
              setSessionId(meta.session_id)
            }
            if (meta.trace_id) {
              metadataRef.current.trace_id = meta.trace_id
            }
          },
          onToken: (token) => {
            rawEventsRef.current.push({ type: 'token', timestamp: new Date().toISOString(), payload: { content: token } })
            accumulatedRef.current += token
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: accumulatedRef.current }
              }
              return updated
            })
          },
          onSources: (sources) => {
            rawEventsRef.current.push({ type: 'sources', timestamp: new Date().toISOString(), payload: { sources } })
            metadataRef.current.sources = sources
          },
          onToolCall: (info) => {
            rawEventsRef.current.push({ type: 'tool_call', timestamp: new Date().toISOString(), payload: info })
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                const existing = last.tool_calls ?? []
                updated[updated.length - 1] = {
                  ...last,
                  tool_calls: [...existing, info] as ChatMessage['tool_calls'],
                }
              }
              return updated
            })
          },
          onDone: (response) => {
            rawEventsRef.current.push({ type: 'done', timestamp: new Date().toISOString(), payload: response })
            setRawEvents([...rawEventsRef.current])
            const meta = response
            if (meta.session_id) {
              setSessionId(meta.session_id)
            }
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  content: accumulatedRef.current,
                  usage: meta.usage ?? null,
                  sources: (meta.sources ?? metadataRef.current.sources) as ChatMessage['sources'],
                  tool_calls: (meta.tool_calls ?? null) as ChatMessage['tool_calls'],
                  model: meta.model ?? null,
                  provider: meta.provider ?? null,
                  latency_ms: meta.latency_ms ?? null,
                  trace_id: meta.trace_id ?? null,
                  parsed_output: meta.parsed_output ?? null,
                }
              }
              return updated
            })
            setLastResponse(meta as AskResponse)
            refetchSessions()
            refetchTraces()
            if (meta.session_id) {
              queryClient.invalidateQueries({ queryKey: ['session-messages', meta.session_id] })
              syncedSessionRef.current = meta.session_id
            }
            if (meta.trace_id) {
              setTimeout(() => setSelectedTraceId(meta.trace_id!), 100)
            }
          },
          onError: (error) => {
            rawEventsRef.current.push({ type: 'error', timestamp: new Date().toISOString(), payload: { message: error.message } })
            setRawEvents([...rawEventsRef.current])
            toast.error(error.message)
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant' && !last.content) {
                updated[updated.length - 1] = {
                  ...last,
                  content: 'Error: Failed to get response. Check your agent configuration.',
                }
              }
              return updated
            })
          },
          onFallback: (info) => {
            rawEventsRef.current.push({ type: 'fallback', timestamp: new Date().toISOString(), payload: info })
            accumulatedRef.current = ''
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: '' }
              }
              return updated
            })
            toast.info(
              `Primary model (${info.primary_provider}/${info.primary_model}) failed. Retrying with ${info.fallback_provider}/${info.fallback_model}...`,
            )
          },
        },
      )
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      toast.error(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setIsSending(false)
    }
  }

  const handleLeftPanelTabChange = (tab: LeftPanelTab) => {
    if (leftPanelTab === tab) {
      setShowLeftPanel(!showLeftPanel)
    } else {
      setLeftPanelTab(tab)
      setShowLeftPanel(true)
      setSelectedTraceId(null)
    }
  }

  const traces = useMemo(() => {
    const mapped: TraceItem[] = backendTraces.map((t) => {
      const traceData = (t.data ?? {}) as Record<string, unknown>
      return {
        id: t.id,
        title: t.status === 'failed' ? `Failed (${t.error?.slice(0, 40) || 'error'})` : `Trace ${t.status}`,
        timestamp: t.created_at ?? new Date().toISOString(),
        status: t.status === 'failed' ? 'error' as const : t.status === 'running' ? 'warning' as const : 'success' as const,
        latency_ms: t.total_latency_ms ?? null,
        model: t.model ?? null,
        provider: t.provider ?? null,
        input_tokens: (traceData.input_tokens as number) ?? null,
        output_tokens: (traceData.output_tokens as number) ?? null,
        total_tokens: (traceData.total_tokens as number) ?? null,
        cost_usd: (traceData.cost_usd as number) ?? t.total_cost_usd ?? null,
        trace_id: t.id,
        response: null,
        project_id: t.project_id,
        agent_id: t.agent_id,
      }
    })
    mapped.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    return mapped
  }, [backendTraces])

  if (agentLoading) return <LoadingState />
  if (agentError) return <ErrorState message="Failed to load agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  let statusLabel: string
  let statusModified: boolean

  if (isDirty) {
    statusLabel = 'Using: Draft (unsaved)'
    statusModified = true
  } else {
    statusLabel = 'Using: Current Draft'
    statusModified = false
  }

  return (
    <ErrorBoundary>
      <div className="-m-6 h-[calc(100vh-3.5rem)] overflow-hidden flex flex-col bg-background">
        <PlaygroundHeader
          agent={agent}
          sessions={sessions}
          sessionId={sessionId}
          showLeftPanel={showLeftPanel}
          showRightPanel={showRightPanel}
          onToggleLeftPanel={() => setShowLeftPanel(!showLeftPanel)}
          onToggleRightPanel={() => setShowRightPanel(!showRightPanel)}
          onNewSession={handleNewSession}
          onSessionSelect={handleSessionSelect}
          onApiClick={() => setShowApiModal(true)}
          onSettingsClick={() => navigate(p(projectId!, 'agents', agentId!, 'edit'))}
          releaseVersion={releaseVersion}
          releaseStatus={releaseStatus}
        />
        <div className="h-6 shrink-0 flex items-center px-4 border-b border-border text-[10px] bg-surface/30">
          <span className="text-muted font-medium">{statusLabel}</span>
          {statusModified && (
            <span className="ml-2 text-yellow-400 font-medium">· unsaved changes</span>
          )}
          <span className="ml-4 text-xs font-medium px-2 py-0.5 rounded-full bg-surface border border-border text-foreground">
            {state.sessionMode === 'stateful' ? 'Stateful' : 'Stateless'}
            <span className="ml-1 text-muted text-[10px]">({activeSource === 'draft_unsaved' ? 'draft' : 'saved'})</span>
          </span>
          <span className="ml-auto text-muted">
            {state.provider}/{state.model}
          </span>
        </div>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          <OperationsRail
            activeTab={showLeftPanel ? leftPanelTab : null}
            onTabChange={handleLeftPanelTabChange}
            onCollapse={() => setShowLeftPanel(false)}
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
              sessionId={sessionId}
              onSelectTrace={setSelectedTraceId}
              onNewSession={handleNewSession}
              onSelectSession={handleSessionSelect}
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
              onSend={handleSend}
              agentName={agent?.name}
            />
          </div>

          {showRightPanel && (
            <AgentInspector
              agent={agent}
              projectId={projectId!}
              agentId={agentId!}
              activeTab={rightPanelTab}
              onTabChange={setRightPanelTab}
              onCollapse={() => setShowRightPanel(false)}
            />
          )}
        </div>
      </div>

      <ApiModal
        open={showApiModal}
        onClose={() => setShowApiModal(false)}
        agent={agent}
        projectId={projectId!}
        orgProjectPathFn={(projId, ...segments) => p(projId, ...segments)}
      />
    </ErrorBoundary>
  )
}

export default function AgentPlaygroundPage() {
  const { projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const { data: agent, isLoading } = useAgent(agentId)

  if (isLoading) return <LoadingState />
  if (!agent) return <ErrorState message="Agent not found" />

  return (
    <AgentEditorProvider agent={agent} projectId={projectId}>
      <PlaygroundContent />
    </AgentEditorProvider>
  )
}
