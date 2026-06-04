import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent } from '@/features/agents/hooks'
import { useAsk } from '@/features/playground/hooks'
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
  const askMutation = useAsk()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<AskResponse | null>(null)
  const [sidePanelTab, setSidePanelTab] = useState<string | undefined>(undefined)

  const handleSend = async (content: string) => {
    if (isSending || !agent) return

    const userMsg: ChatMessage = { role: 'user', content }

    let assistantMsg: ChatMessage = {
      role: 'assistant',
      content: '',
    }

    setMessages((prev) => [...prev, userMsg])
    setIsSending(true)

    try {
      const res: AskResponse = await askMutation.mutateAsync({
        project_id: projectId!,
        agent_id: agentId!,
        message: content,
        session_id: sessionId,
      })

      if (res.session_id) {
        setSessionId(res.session_id)
      }

      assistantMsg = {
        role: 'assistant',
        content: res.answer,
        usage: res.usage,
        sources: res.sources,
      }
      setMessages((prev) => [...prev, assistantMsg])
      setLastResponse(res)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Request failed')
      assistantMsg = {
        role: 'assistant',
        content: 'Error: Failed to get response. Check your agent configuration.',
      }
      setMessages((prev) => [...prev, assistantMsg])
    } finally {
      setIsSending(false)
    }
  }

  const handleNewSession = () => {
    setSessionId(null)
    setMessages([])
    setLastResponse(null)
  }

  const handleClear = () => {
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
              onClick={() => navigate(p(projectId!, 'agents', agentId!))}
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
