import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAgent } from '@/features/agents/hooks'
import { useAsk, useCreateSession } from '@/features/playground/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Textarea'
import { Separator } from '@/components/ui/Separator'
import { CopyButton } from '@/components/common/CopyButton'
import { orgProjectPath } from '@/lib/constants/routes'
import { Send, Trash2, Plus, Bot, User, Info, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  usage?: { input_tokens: number; output_tokens: number; cost_usd: number }
}

export default function AgentPlaygroundPage() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading: agentLoading, isError: agentError } = useAgent(agentId)

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)
  const createSession = useCreateSession()
  const askMutation = useAsk()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [debugOpen, setDebugOpen] = useState(false)
  const [lastResponse, setLastResponse] = useState<Record<string, unknown> | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isSending || !agent) return

    const userMsg: ChatMessage = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsSending(true)

    try {
      let sid = sessionId
      if (!sid) {
        const session = await createSession.mutateAsync({
          project_id: projectId!,
          agent_id: agentId!,
          mode: 'chat',
        })
        sid = session.id
        setSessionId(sid)
      }

      const res = await askMutation.mutateAsync({
        session_id: sid,
        content: userMsg.content,
      })

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: res.answer,
        usage: res.usage,
      }
      setMessages((prev) => [...prev, assistantMsg])
      setLastResponse(res as unknown as Record<string, unknown>)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Request failed')
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error: Failed to get response. Check your agent configuration.' },
      ])
    } finally {
      setIsSending(false)
    }
  }

  const handleNewSession = () => {
    setSessionId(null)
    setMessages([])
    setLastResponse(null)
  }

  if (agentLoading) return <LoadingState />
  if (agentError) return <ErrorState message="Failed to load agent" onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Playground"
        description={`${agent.name} · ${agent.provider}/${agent.model}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleNewSession}>
              <Plus className="mr-1 h-4 w-4" />
              New Session
            </Button>
            <Button variant="outline" size="sm" onClick={() => setMessages([])}>
              <Trash2 className="mr-1 h-4 w-4" />
              Clear
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDebugOpen(!debugOpen)}
            >
              <Info className="mr-1 h-4 w-4" />
              Debug
            </Button>
          </div>
        }
      />

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="flex-1 flex flex-col">
          <Card className="flex-1 flex flex-col overflow-hidden">
            <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="flex items-center justify-center h-full text-center">
                  <div>
                    <Bot className="mx-auto h-10 w-10 text-muted mb-3" />
                    <p className="text-muted text-sm">Send a message to start testing your agent.</p>
                    <p className="text-muted text-xs mt-1">Session mode: chat</p>
                  </div>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-1' : ''}`}>
                    <div
                      className={`rounded-lg px-4 py-3 text-sm ${
                        msg.role === 'user'
                          ? 'bg-primary text-white'
                          : 'bg-accent text-white'
                      }`}
                    >
                      {msg.content}
                    </div>
                    {msg.usage && (
                      <p className="text-xs text-muted mt-1">
                        {msg.usage.input_tokens} in / {msg.usage.output_tokens} out · ${msg.usage.cost_usd.toFixed(6)}
                      </p>
                    )}
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent shrink-0">
                    {msg.role === 'user' ? (
                      <User className="h-4 w-4 text-muted" />
                    ) : (
                      <Bot className="h-4 w-4 text-primary" />
                    )}
                  </div>
                </div>
              ))}
              {isSending && (
                <div className="flex gap-3">
                  <div className="max-w-[80%]">
                    <div className="rounded-lg px-4 py-3 bg-accent">
                      <Loader2 className="h-4 w-4 animate-spin text-muted" />
                    </div>
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent shrink-0">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </CardContent>

            <div className="border-t border-border p-4">
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your message..."
                  className="min-h-[44px] max-h-[120px]"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                />
                <Button onClick={handleSend} loading={isSending} className="h-[44px]">
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        </div>

        {debugOpen && (
          <div className="w-80 shrink-0 overflow-y-auto">
            <Card>
              <CardContent className="p-4 space-y-4">
                <div>
                  <p className="text-xs font-medium text-muted mb-2">Session</p>
                  <p className="text-xs text-white break-all">{sessionId || 'No active session'}</p>
                </div>
                <Separator />
                <div>
                  <p className="text-xs font-medium text-muted mb-2">Agent</p>
                  <p className="text-xs text-white">{agent.name}</p>
                  <p className="text-xs text-muted">{agent.provider}/{agent.model}</p>
                </div>
                <Separator />
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-medium text-muted">Response</p>
                    {lastResponse && <CopyButton text={JSON.stringify(lastResponse, null, 2)} />}
                  </div>
                  <pre className="text-xs text-muted overflow-x-auto max-h-60">
                    {lastResponse ? JSON.stringify(lastResponse, null, 2) : '—'}
                  </pre>
                </div>
                <Separator />
                <div>
                  <p className="text-xs font-medium text-muted mb-2">Messages: {messages.length}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
