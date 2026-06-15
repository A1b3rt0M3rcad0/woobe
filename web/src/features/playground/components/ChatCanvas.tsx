import { useRef, useEffect } from 'react'
import { Bot, ArrowRight } from 'lucide-react'
import { ChatMessage } from './ChatMessage'
import { ChatComposer } from './ChatComposer'
import { ScrollArea } from '@/components/ui/ScrollArea'
import type { ChatMessage as ChatMessageType } from '@/features/playground/types'

interface ChatCanvasProps {
  messages: ChatMessageType[]
  isSending: boolean
  onSend: (content: string) => void
  agentName?: string
}

const suggestions = [
  'Summarize the latest user activity',
  'Explain the authentication flow',
  'Show me an example API response',
]

export function ChatCanvas({ messages, isSending, onSend, agentName }: ChatCanvasProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages.length])

  const isEmpty = messages.length === 0

  return (
    <section className="flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden bg-background">
      <ScrollArea
        ref={messagesContainerRef}
        className="flex-1 min-h-0 relative"
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.06) 0%, transparent 70%)',
          }}
        />

        {isEmpty ? (
          <div className="relative flex flex-col items-center justify-center h-full px-6 text-center">
            <div className="rounded-full bg-primary/10 p-4 mb-4">
              <Bot className="h-8 w-8 text-primary" />
            </div>
            <h2 className="text-lg font-semibold text-white mb-1">
              Start a conversation with your agent
            </h2>
            <p className="text-sm text-muted max-w-md mb-6">
              Ask anything, test capabilities, and iterate.
            </p>
            <div className="flex flex-col gap-2 w-full max-w-sm">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => onSend(suggestion)}
                  className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-3 text-sm text-muted hover:text-white hover:border-primary/30 hover:bg-primary/5 transition-all text-left"
                >
                  <span>{suggestion}</span>
                  <ArrowRight className="h-4 w-4 shrink-0 ml-2" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="relative space-y-4 p-4 pb-2">
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                isStreaming={msg.role === 'assistant' && isSending && i === messages.length - 1}
                isLast={i === messages.length - 1}
                agentName={agentName}
              />
            ))}
            <div />
          </div>
        )}
      </ScrollArea>

      <ChatComposer isSending={isSending} onSend={onSend} />
    </section>
  )
}
