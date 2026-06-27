import { useState } from 'react'
import { Bot, User, ChevronDown, ChevronRight, Loader2, Copy, ThumbsUp, ThumbsDown, AlertCircle } from 'lucide-react'
import { formatNumber, formatLatency } from '@/lib/formatters/number'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { StructuredJsonResponse } from './StructuredJsonResponse'
import { ToolCallsCollapsible } from './ToolCallsCollapsible'
import { MarkdownMessage } from './MarkdownMessage'
import { parseAssistantMessageContent } from '@/lib/parse-assistant-message'
import type { AgentActivityInfo, ChatMessage as ChatMessageType } from '@/features/playground/types'

interface ChatMessageProps {
  message: ChatMessageType
  isStreaming?: boolean
  isLast?: boolean
  agentName?: string
}

function SourcesCollapsible({ sources }: { sources: NonNullable<ChatMessageType['sources']> }) {
  const [open, setOpen] = useState(false)
  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-primary-light hover:text-white transition-colors"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Sources ({sources.length})
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {sources.map((s, i) => (
            <div key={i} className="rounded-lg border border-border/80 bg-background/60 p-2 text-xs">
              <p className="font-medium text-white">{s.document_title || 'Untitled'}</p>
              {s.page_number != null && <p className="text-muted">Page {s.page_number}</p>}
              {s.content_preview && (
                <p className="text-muted mt-0.5 italic">&quot;{s.content_preview.slice(0, 200)}...&quot;</p>
              )}
              {s.score != null && <p className="text-muted">Score: {formatNumber(s.score, 3)}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function activityMessage(activity?: AgentActivityInfo | null): string {
  if (activity?.message) return activity.message
  if (activity?.status === 'planning_tools') return 'Checking whether tools are needed...'
  if (activity?.status === 'calling_tool') return activity.tool_name ? `Calling tool: ${activity.tool_name}...` : 'Calling tool...'
  if (activity?.status === 'processing_tool_result') return 'Processing tool result...'
  if (activity?.status === 'generating_answer') return 'Generating response...'
  if (activity?.status === 'formatting_response') return 'Formatting structured response...'
  return 'Working...'
}

function ActivityBubble({ activity }: { activity?: AgentActivityInfo | null }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-xl border border-border/80 bg-surface/70 px-4 py-3 text-sm text-muted shadow-sm shadow-black/5">
      <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
      {activityMessage(activity)}
    </div>
  )
}

function AssistantContent({ message, isStreaming }: { message: ChatMessageType; isStreaming?: boolean }) {
  if (isStreaming && !message.content) {
    return <ActivityBubble activity={message.activity} />
  }

  if (!isStreaming && message.parsed_output) {
    return <StructuredJsonResponse value={message.parsed_output} />
  }

  const { isPureJson, segments } = parseAssistantMessageContent(message.content)
  if (isPureJson && segments[0].type === 'json') {
    return <StructuredJsonResponse value={segments[0].value} raw={segments[0].raw} />
  }

  if (segments.length === 1 && segments[0].type === 'text') {
    return (
      <div className="rounded-xl rounded-bl-md border border-border/80 bg-surface/75 px-4 py-3 text-sm leading-relaxed text-white shadow-sm shadow-black/5">
        <MarkdownMessage content={segments[0].content} isStreaming={isStreaming} />
      </div>
    )
  }

  return (
    <div className="rounded-xl rounded-bl-md border border-border/80 bg-surface/75 px-4 py-3 text-sm leading-relaxed text-white shadow-sm shadow-black/5">
      <div className="space-y-2">
        {segments.map((seg, i) =>
          seg.type === 'text' ? (
            <MarkdownMessage key={i} content={seg.content} />
          ) : (
            <div key={i} className="my-2">
              <JsonCodeBlock value={seg.value} maxHeight={160} />
            </div>
          )
        )}
        {isStreaming && (
          <span className="inline-flex h-3 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-primary/80" aria-label="Streaming" />
        )}
      </div>
    </div>
  )
}

export function ChatMessage({ message, isStreaming, isLast: _isLast, agentName }: ChatMessageProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex gap-3 justify-end overflow-hidden">
        <div className="max-w-[80%]">
          <div className="rounded-xl rounded-br-md border border-primary/25 bg-primary/10 px-4 py-3 text-sm leading-relaxed text-white whitespace-pre-wrap break-words shadow-sm shadow-black/5">
            {message.content}
          </div>
        </div>
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-primary/25 bg-primary/10 shrink-0">
          <User className="h-4 w-4 text-primary-light" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-3 justify-start overflow-hidden">
        <div className="flex flex-col items-center gap-1.5 shrink-0 w-14">
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface shrink-0">
            <Bot className="h-4 w-4 text-primary-light" />
          </div>
          {agentName && (
            <span
              className="text-[10px] text-muted text-center leading-tight truncate w-full"
              title={agentName}
            >
              {agentName}
            </span>
          )}
        </div>

        <div className="max-w-[80%] space-y-1.5">
          <AssistantContent message={message} isStreaming={isStreaming} />
          {isStreaming && message.content && message.activity && (
            <ActivityBubble activity={message.activity} />
          )}
        </div>
      </div>

      {message.tool_calls && message.tool_calls.length > 0 && (
        <div className="pl-16 space-y-1.5">
          <ToolCallsCollapsible toolCalls={message.tool_calls} />
        </div>
      )}

      {!isStreaming && (
        <div className="pl-16 space-y-1.5">
          {message.output_parse_error && (
            <div className="flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-[11px] leading-relaxed text-amber-200">
              <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              <span>{message.output_parse_error}</span>
            </div>
          )}
          {message.sources && message.sources.length > 0 && (
            <SourcesCollapsible sources={message.sources} />
          )}

          <div className="flex items-center gap-3 text-[11px] text-muted">
            {message.model && (
              <span>{message.provider || ''} {message.model}</span>
            )}
            {message.latency_ms != null && (
              <span>{formatLatency(message.latency_ms)}</span>
            )}
            {message.usage && (
              <span>
                {formatNumber(message.usage.input_tokens, 0)} in / {formatNumber(message.usage.output_tokens, 0)} out
              </span>
            )}
            {message.trace_id && (
              <span className="font-mono">{message.trace_id.slice(0, 8)}...</span>
            )}
          </div>

          <div className="flex items-center gap-1">
            <button className="flex h-6 w-6 items-center justify-center rounded-md border border-transparent text-muted hover:text-white hover:border-border/80 hover:bg-background/70 transition-colors" title="Copy">
              <Copy className="h-3 w-3" />
            </button>
            <button className="flex h-6 w-6 items-center justify-center rounded-md border border-transparent text-muted hover:text-emerald-300 hover:border-emerald-500/30 hover:bg-emerald-500/10 transition-colors" title="Good response">
              <ThumbsUp className="h-3 w-3" />
            </button>
            <button className="flex h-6 w-6 items-center justify-center rounded-md border border-transparent text-muted hover:text-red-300 hover:border-red-500/30 hover:bg-red-500/10 transition-colors" title="Bad response">
              <ThumbsDown className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
