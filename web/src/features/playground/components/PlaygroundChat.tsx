import { useRef, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Textarea'
import { Send, Plus, Trash2, Bot, User, Loader2, ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { formatNumber, formatCurrency } from '@/lib/formatters/number'
import type { SourceInfo } from '@/features/playground/types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  usage?: { input_tokens: number | null; output_tokens: number | null; cost_usd: number | null } | null
  sources?: SourceInfo[] | null
}

interface PlaygroundChatProps {
  messages: ChatMessage[]
  isSending: boolean
  sessionId: string | null
  onSend: (content: string) => void
  onNewSession: () => void
  onClear: () => void
}

function SourcesCollapsible({ sources }: { sources: SourceInfo[] }) {
  const [open, setOpen] = useState(false)
  if (!sources || sources.length === 0) return null
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-primary hover:underline"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Sources ({sources.length})
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {sources.map((s, i) => (
            <div key={i} className="rounded border border-border bg-background p-2 text-xs">
              <p className="font-medium text-white">{s.document_title || 'Untitled'}</p>
              {s.page_number != null && <p className="text-muted">Page {s.page_number}</p>}
              {s.chunk_preview && <p className="text-muted mt-0.5 italic">"{s.chunk_preview.slice(0, 200)}..."</p>}
              {s.score != null && <p className="text-muted">Score: {formatNumber(s.score, 3)}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function PlaygroundChat({ messages, isSending, sessionId, onSend, onNewSession, onClear }: PlaygroundChatProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || isSending) return
    onSend(input.trim())
    setInput('')
  }

  return (
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
              {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                <SourcesCollapsible sources={msg.sources} />
              )}
              {msg.usage && (
                <p className="text-xs text-muted mt-1">
                  {formatNumber(msg.usage.input_tokens, 0)} in / {formatNumber(msg.usage.output_tokens, 0)} out · {formatCurrency(msg.usage.cost_usd, 6)}
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
        <div className="flex gap-2 mt-2">
          <Button variant="outline" size="sm" onClick={onNewSession}>
            <Plus className="mr-1 h-4 w-4" />
            New Session
          </Button>
          <Button variant="outline" size="sm" onClick={onClear}>
            <Trash2 className="mr-1 h-4 w-4" />
            Clear
          </Button>
        </div>
      </div>
    </Card>
  )
}
