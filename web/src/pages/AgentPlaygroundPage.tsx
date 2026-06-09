import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent } from '@/features/agents/hooks'
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
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { AskResponse, SessionListItem, ChatMessage, TraceItem } from '@/features/playground/types'

function formatSessionLabel(s: SessionListItem): string {
  const date = s.last_message_at
    ? new Date(s.last_message_at)
    : s.created_at
      ? new Date(s.created_at)
      : null
  const dateStr = date
    ? date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Unknown'
  const msgCount = s.message_count ?? 0
  return `${dateStr} (${msgCount} msg${msgCount !== 1 ? 's' : ''})`
}

function buildTraces(messages: ChatMessage[], lastResponse: AskResponse | null, sessionId: string | null): TraceItem[] {
  if (!lastResponse || messages.length === 0) return []
  const assistantMsgs = messages.filter(m => m.role === 'assistant' && m.content)
  return assistantMsgs.map((msg, i) => ({
    id: `trace-${i}-${msg.trace_id || Date.now()}`,
    title: msg.content.slice(0, 60).replace(/\n/g, ' ') + (msg.content.length > 60 ? '...' : ''),
    timestamp: new Date().toISOString(),
    status: msg.content.startsWith('Error') ? 'error' as const : 'success' as const,
    latency_ms: msg.latency_ms ?? null,
    model: msg.model ?? null,
    provider: msg.provider ?? null,
    input_tokens: msg.usage?.input_tokens ?? null,
    output_tokens: msg.usage?.output_tokens ?? null,
    total_tokens: msg.usage?.total_tokens ?? null,
    cost_usd: msg.usage?.cost_usd ?? null,
    trace_id: msg.trace_id ?? null,
    response: i === assistantMsgs.length - 1 ? lastResponse : null,
  }))
}

export default function AgentPlaygroundPage() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)
  const { stream, cancel: cancelStream } = useAskStream()
  const queryClient = useQueryClient()

  const { data: sessions = [], refetch: refetchSessions } = useAgentSessions(agentId, projectId)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null)

  const [leftPanelTab, setLeftPanelTab] = useState<LeftPanelTab | null>('debug')
  const [showLeftPanel, setShowLeftPanel] = useState(true)
  const [showRightPanel, setShowRightPanel] = useState(true)
  const [rightPanelTab, setRightPanelTab] = useState('agent')
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [showApiModal, setShowApiModal] = useState(false)

  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})

  const {
    data: backendTraces = [],
    isLoading: tracesLoading,
    isError: tracesError,
    error: tracesQueryError,
    refetch: refetchTraces,
  } = usePlaygroundTraces(projectId, agentId, sessionId)

  const selectedSessionId = sessionId
  const { data: historyMessages, refetch: refetchHistory } = useSessionMessages(
    selectedSessionId ?? undefined,
  )

  useEffect(() => {
    if (historyMessages && selectedSessionId) {
      const mapped: ChatMessage[] = historyMessages.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        usage: m.input_tokens != null ? { input_tokens: m.input_tokens, output_tokens: m.output_tokens ?? null, cost_usd: null } : null,
        ...(m.role === 'assistant' ? { model: null, provider: null } : {}),
      }))
      setMessages(mapped)
    }
  }, [historyMessages, selectedSessionId])

  const handleSessionSelect = useCallback((sessionIdValue: string) => {
    cancelStream()
    setSessionId(sessionIdValue)
    setLastResponse(null)
    setSelectedTraceId(null)
  }, [cancelStream])

  const handleNewSession = useCallback(() => {
    cancelStream()
    setSessionId(null)
    setMessages([])
    setLastResponse(null)
    setSelectedTraceId(null)
  }, [cancelStream])

  const handleSend = async (content: string) => {
    if (isSending || !agent) return

    accumulatedRef.current = ''
    metadataRef.current = {}

    const userMsg: ChatMessage = { role: 'user', content }
    const assistantMsg: ChatMessage = { role: 'assistant', content: '' }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsSending(true)

    try {
      await stream(
        {
          project_id: projectId!,
          agent_id: agentId!,
          message: content,
          session_id: sessionId,
        },
        {
          onMeta: (meta) => {
            if (meta.session_id) {
              setSessionId(meta.session_id)
            }
          },
          onToken: (token) => {
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
            metadataRef.current.sources = sources
          },
          onDone: (response) => {
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
              setTimeout(() => refetchHistory(), 100)
            }
          },
          onError: (error) => {
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

  const localTraces = buildTraces(messages, lastResponse, sessionId)

  const traces = useMemo(() => {
    const backendMapped: TraceItem[] = backendTraces.map((t) => ({
      id: t.id,
      title: t.status === 'failed' ? `Failed (${t.error?.slice(0, 40) || 'error'})` : `Trace ${t.status}`,
      timestamp: t.created_at ?? new Date().toISOString(),
      status: t.status === 'failed' ? 'error' as const : t.status === 'running' ? 'warning' as const : 'success' as const,
      latency_ms: t.total_latency_ms ?? null,
      model: t.model ?? null,
      provider: t.provider ?? null,
      input_tokens: null,
      output_tokens: null,
      total_tokens: null,
      cost_usd: t.total_cost_usd ?? null,
      trace_id: t.id,
      response: null,
    }))

    const localIds = new Set(localTraces.map((lt) => lt.trace_id).filter(Boolean))
    const merged = [...backendMapped.filter((bt) => !localIds.has(bt.trace_id)), ...localTraces]
    merged.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    return merged
  }, [backendTraces, localTraces])

  if (agentLoading) return <LoadingState />
  if (agentError) return <ErrorState message="Failed to load agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

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
        />

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
