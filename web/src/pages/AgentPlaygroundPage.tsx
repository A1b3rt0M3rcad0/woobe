import { useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent } from '@/features/agents/hooks'
import { useAskStream } from '@/features/playground/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { orgProjectPath } from '@/lib/constants/routes'
import { PlaygroundChat, type ChatMessage } from '@/features/playground/components/PlaygroundChat'
import { PlaygroundSidePanel } from '@/features/playground/components/PlaygroundSidePanel'
import { Code2, Settings } from 'lucide-react'
import { toast } from 'sonner'
import type { AskResponse } from '@/features/playground/types'

export default function AgentPlaygroundPage() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)
  const { stream, cancel: cancelStream } = useAskStream()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null)
  const [sidePanelTab, setSidePanelTab] = useState<string | undefined>(undefined)

  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})

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

  const handleNewSession = () => {
    cancelStream()
    setSessionId(null)
    setMessages([])
    setLastResponse(null)
  }

  const handleClear = () => {
    cancelStream()
    setMessages([])
    setLastResponse(null)
  }

  if (agentLoading) return <LoadingState />
  if (agentError) return <ErrorState message="Failed to load agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

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
