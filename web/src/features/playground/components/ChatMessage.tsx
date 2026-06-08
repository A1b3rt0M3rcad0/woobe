import { useState } from 'react'
import { Bot, User, ChevronDown, ChevronRight, Loader2, Copy, ThumbsUp, ThumbsDown } from 'lucide-react'
import { formatNumber, formatCurrency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'
import { JsonCodeBlock } from './JsonCodeBlock'
import type { ChatMessage as ChatMessageType } from '@/features/playground/types'

interface ChatMessageProps {
  message: ChatMessageType
  isStreaming?: boolean
  isLast?: boolean
}

function SourcesCollapsible({ sources }: { sources: NonNullable<ChatMessageType['sources']> }) {
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
              {s.content_preview && (
                <p className="text-muted mt-0.5 italic">"{s.content_preview.slice(0, 200)}..."</p>
              )}
              {s.score != null && <p className="text-muted">Score: {formatNumber(s.score, 3)}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ChatMessage({ message, isStreaming, isLast }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex gap-3 overflow-hidden', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('max-w-[80%]', isUser ? 'order-1' : 'order-1')}>
        {isStreaming ? (
          <div className="flex items-center gap-2 rounded-lg bg-accent px-4 py-3 text-sm text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking...
          </div>
        ) : (
          <div
            className={cn(
              'rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words',
              isUser
                ? 'bg-primary text-white rounded-br-md'
                : 'bg-accent text-white rounded-bl-md',
            )}
          >
            {message.content}
          </div>
        )}

        {!isUser && !isStreaming && (
          <>
            {message.sources && message.sources.length > 0 && (
              <SourcesCollapsible sources={message.sources} />
            )}

            {message.parsed_output && (
              <div className="mt-2">
                <JsonCodeBlock
                  data={message.parsed_output}
                  title="Structured Output"
                  maxHeight="max-h-40"
                  className="border-l-2 border-emerald-500/30 pl-2"
                />
              </div>
            )}

            <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted">
              {message.model && (
                <span>{message.provider || ''} {message.model}</span>
              )}
              {message.latency_ms != null && (
                <span>{Math.round(message.latency_ms)}ms</span>
              )}
              {message.usage && (
                <span>
                  {formatNumber(message.usage.input_tokens, 0)} in / {formatNumber(message.usage.output_tokens, 0)} out · {formatCurrency(message.usage.cost_usd, 6)}
                </span>
              )}
              {message.trace_id && (
                <span className="font-mono">{message.trace_id.slice(0, 8)}...</span>
              )}
            </div>

            <div className="mt-1 flex items-center gap-1">
              <button className="p-1 rounded text-muted hover:text-white hover:bg-accent transition-colors" title="Copy">
                <Copy className="h-3 w-3" />
              </button>
              <button className="p-1 rounded text-muted hover:text-emerald-400 hover:bg-accent transition-colors" title="Good response">
                <ThumbsUp className="h-3 w-3" />
              </button>
              <button className="p-1 rounded text-muted hover:text-red-400 hover:bg-accent transition-colors" title="Bad response">
                <ThumbsDown className="h-3 w-3" />
              </button>
            </div>
          </>
        )}
      </div>

      <div className={cn(
        'flex h-8 w-8 items-center justify-center rounded-full shrink-0',
        isUser ? 'bg-primary/10' : 'bg-accent',
        isUser ? 'order-2' : 'order-2',
      )}>
        {isUser ? (
          <User className="h-4 w-4 text-primary" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>
    </div>
  )
}
