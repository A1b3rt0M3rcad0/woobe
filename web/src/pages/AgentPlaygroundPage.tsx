import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent } from '@/features/agents/hooks'
import { useAskStream, useAgentSessions, useSessionMessages } from '@/features/playground/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { orgProjectPath } from '@/lib/constants/routes'
import { PlaygroundChat, type ChatMessage } from '@/features/playground/components/PlaygroundChat'
import { PlaygroundSidePanel } from '@/features/playground/components/PlaygroundSidePanel'
import { Code2, Settings, History } from 'lucide-react'
import { toast } from 'sonner'
import type { AskResponse, SessionListItem } from '@/features/playground/types'

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

export default function AgentPlaygroundPage() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)
  const { stream, cancel: cancelStream } = useAskStream()

  const { data: sessions = [], refetch: refetchSessions } = useAgentSessions(agentId, projectId)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null)
  const [sidePanelTab, setSidePanelTab] = useState<string | undefined>(undefined)

  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})
  const sessionsLoadedRef = useRef(false)

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
  }, [cancelStream])

  const handleNewSession = useCallback(() => {
    cancelStream()
    setSessionId(null)
    setMessages([])
    setLastResponse(null)
  }, [cancelStream])

  const handleClear = useCallback(() => {
    cancelStream()
    setMessages([])
    setLastResponse(null)
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
                }
              }
              return updated
            })
            setLastResponse(meta as AskResponse)
            refetchSessions()
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

  if (agentLoading) return <LoadingState />
  if (agentError) return <ErrorState message="Failed to load agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  const sessionOptions = sessions.map((s) => ({
    value: s.id,
    label: formatSessionLabel(s),
  }))

  return (
    <ErrorBoundary>
    <div className="flex flex-col h-full">
      <PageHeader
        title={agent.name}
        description={
          <span className="flex items-center gap-2">
            <span>{agent.provider}/{agent.model}</span>
            <StatusBadge status={agent.status} />
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <History className="h-4 w-4 text-muted" />
              <Select
                value={selectedSessionId ?? ''}
                onChange={(e) => {
                  const val = e.target.value
                  if (val === '__new__') {
                    handleNewSession()
                  } else {
                    handleSessionSelect(val)
                  }
                }}
                options={[
                  { value: '__new__', label: '+ New Session' },
                  ...sessionOptions,
                ]}
                className="min-w-[200px]"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSidePanelTab('api')}
            >
              <Code2 className="mr-1 h-4 w-4" />
              API
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(p(projectId!, 'agents', agentId!, 'edit'))}
            >
              <Settings className="mr-1 h-4 w-4" />
              Settings
            </Button>
          </div>
        }
      />

      <div className="flex flex-1 gap-0 overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0">
          <PlaygroundChat
            messages={messages}
            isSending={isSending}
            sessionId={sessionId}
            onSend={handleSend}
            onNewSession={handleNewSession}
            onClear={handleClear}
          />
        </div>

        <PlaygroundSidePanel
          agent={agent}
          projectId={projectId!}
          agentId={agentId!}
          organizationId={organizationId}
          lastResponse={lastResponse}
          sessionId={sessionId}
          messagesCount={messages.length}
          orgProjectPathFn={(projId, ...segments) => p(projId, ...segments)}
        />
      </div>
    </div>
    </ErrorBoundary>
  )
}
