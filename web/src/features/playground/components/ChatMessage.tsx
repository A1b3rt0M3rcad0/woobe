import { useState, type ReactNode } from 'react'
import {
  AlertCircle,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Loader2,
  ThumbsDown,
  ThumbsUp,
  User,
  Workflow,
} from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { AgentActivityInfo, ChatMessage as ChatMessageType } from '@/features/playground/types'
import { formatLatency, formatNumber } from '@/lib/formatters/number'
import { parseAssistantMessageContent } from '@/lib/parse-assistant-message'
import { cn } from '@/lib/utils'

import { MarkdownMessage } from './MarkdownMessage'
import { StructuredJsonResponse } from './StructuredJsonResponse'
import { ToolCallsCollapsible } from './ToolCallsCollapsible'

export type ChatMessageVariant = 'playground' | 'network'

interface ChatMessageProps {
  message: ChatMessageType
  isStreaming?: boolean
  isLast?: boolean
  agentName?: string
  variant?: ChatMessageVariant
  assistantIcon?: 'bot' | 'network'
  details?: ReactNode
  footerMeta?: ReactNode
  footerActions?: ReactNode
}

function SourcesCollapsible({
  sources,
  variant,
}: {
  sources: NonNullable<ChatMessageType['sources']>
  variant: ChatMessageVariant
}) {
  const [open, setOpen] = useState(false)
  const compact = variant === 'network'
  if (!sources || sources.length === 0) return null

  return (
    <div className={compact ? 'mt-1.5' : 'mt-2'}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1 text-primary-light transition-colors hover:text-white',
          compact ? 'text-[9px]' : 'text-xs',
        )}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Sources ({sources.length})
      </button>
      {open && (
        <div className={cn('mt-1 space-y-1', compact && 'max-w-full')}>
          {sources.map((source, index) => (
            <div
              key={source.chunk_id || `${source.document_id || 'source'}-${index}`}
              className={cn(
                'rounded-lg border border-border/80 bg-background/60',
                compact ? 'p-2 text-[9px] leading-4' : 'p-2 text-xs',
              )}
            >
              <p className="truncate font-medium text-white">{source.document_title || 'Untitled'}</p>
              {(source.page_number != null || source.score != null) && (
                <div className="mt-0.5 flex flex-wrap gap-x-2 text-muted">
                  {source.page_number != null && <span>Page {source.page_number}</span>}
                  {source.score != null && <span>Score {formatNumber(source.score, 3)}</span>}
                </div>
              )}
              {source.content_preview && (
                <p className={cn('mt-1 italic text-muted', compact ? 'line-clamp-3' : '')}>
                  &quot;{source.content_preview.slice(0, compact ? 160 : 200)}{source.content_preview.length > (compact ? 160 : 200) ? '…' : ''}&quot;
                </p>
              )}
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

function ActivityBubble({
  activity,
  variant,
}: {
  activity?: AgentActivityInfo | null
  variant: ChatMessageVariant
}) {
  const compact = variant === 'network'
  return (
    <div
      className={cn(
        'inline-flex items-center border border-border/80 bg-surface/70 text-muted shadow-sm shadow-black/5',
        compact
          ? 'gap-1.5 rounded-lg px-2.5 py-2 text-[10px] leading-4'
          : 'gap-2 rounded-xl px-4 py-3 text-sm',
      )}
    >
      <Loader2 className={cn('animate-spin text-primary-light', compact ? 'h-3 w-3' : 'h-4 w-4')} />
      {activityMessage(activity)}
    </div>
  )
}

function AssistantContent({
  message,
  isStreaming,
  variant,
}: {
  message: ChatMessageType
  isStreaming?: boolean
  variant: ChatMessageVariant
}) {
  const compact = variant === 'network'

  if (isStreaming && !message.content) {
    return <ActivityBubble activity={message.activity} variant={variant} />
  }

  if (!isStreaming && message.parsed_output) {
    return <StructuredJsonResponse value={message.parsed_output} density={compact ? 'compact' : 'comfortable'} />
  }

  const { isPureJson, segments } = parseAssistantMessageContent(message.content)
  if (!isStreaming && isPureJson && segments[0].type === 'json') {
    return (
      <StructuredJsonResponse
        value={segments[0].value}
        raw={segments[0].raw}
        density={compact ? 'compact' : 'comfortable'}
      />
    )
  }

  if (segments.length === 1 && segments[0].type === 'text') {
    return (
      <div
        className={cn(
          'border border-border/80 bg-surface/75 text-white shadow-sm shadow-black/5',
          compact
            ? 'rounded-lg rounded-bl-sm px-2.5 py-2 text-[10px] leading-4'
            : 'rounded-xl rounded-bl-md px-4 py-3 text-sm leading-relaxed',
        )}
      >
        <MarkdownMessage
          content={segments[0].content}
          isStreaming={isStreaming}
          className={compact ? 'space-y-1.5 text-[10px] leading-4' : undefined}
        />
      </div>
    )
  }

  return (
    <div
      className={cn(
        'border border-border/80 bg-surface/75 text-white shadow-sm shadow-black/5',
        compact
          ? 'rounded-lg rounded-bl-sm px-2.5 py-2 text-[10px] leading-4'
          : 'rounded-xl rounded-bl-md px-4 py-3 text-sm leading-relaxed',
      )}
    >
      <div className={compact ? 'space-y-1.5' : 'space-y-2'}>
        {segments.map((segment, index) =>
          segment.type === 'text' ? (
            <MarkdownMessage
              key={index}
              content={segment.content}
              className={compact ? 'space-y-1.5 text-[10px] leading-4' : undefined}
            />
          ) : (
            <div key={index} className={compact ? 'my-1.5' : 'my-2'}>
              <JsonCodeBlock value={segment.value} maxHeight={compact ? 140 : 160} />
            </div>
          ),
        )}
        {isStreaming && (
          <span
            className="inline-flex h-3 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-primary/80"
            aria-label="Streaming"
          />
        )}
      </div>
    </div>
  )
}

export function ChatMessage({
  message,
  isStreaming,
  isLast: _isLast,
  agentName,
  variant = 'playground',
  assistantIcon = 'bot',
  details,
  footerMeta,
  footerActions,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const compact = variant === 'network'

  if (isUser) {
    return (
      <div className={cn('flex justify-end overflow-hidden', compact ? 'gap-2' : 'gap-3')}>
        <div className={compact ? 'max-w-[88%]' : 'max-w-[80%]'}>
          <div
            className={cn(
              'whitespace-pre-wrap break-words border border-primary/25 bg-primary/10 text-white shadow-sm shadow-black/5',
              compact
                ? 'rounded-lg rounded-br-sm px-2.5 py-2 text-[10px] leading-4'
                : 'rounded-xl rounded-br-md px-4 py-3 text-sm leading-relaxed',
            )}
          >
            {message.content}
          </div>
        </div>
        <div
          className={cn(
            'flex shrink-0 items-center justify-center border border-primary/25 bg-primary/10',
            compact ? 'h-6 w-6 rounded-md' : 'h-8 w-8 rounded-full',
          )}
        >
          <User className={cn('text-primary-light', compact ? 'h-3 w-3' : 'h-4 w-4')} />
        </div>
      </div>
    )
  }

  const copyValue = message.parsed_output
    ? JSON.stringify(message.parsed_output, null, 2)
    : message.content
  const AssistantIcon = assistantIcon === 'network' ? Workflow : Bot

  const copyResponse = async () => {
    if (!copyValue) return
    await navigator.clipboard?.writeText(copyValue)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className={cn('flex flex-col', compact ? 'gap-1' : 'gap-1.5')}>
      <div className={cn('flex justify-start overflow-hidden', compact ? 'gap-2' : 'gap-3')}>
        <div className={cn('flex shrink-0 flex-col items-center', compact ? 'w-6 gap-1' : 'w-14 gap-1.5')}>
          <div
            className={cn(
              'flex shrink-0 items-center justify-center border border-border bg-surface',
              compact ? 'h-6 w-6 rounded-md' : 'h-8 w-8 rounded-full',
            )}
          >
            <AssistantIcon className={cn('text-primary-light', compact ? 'h-3 w-3' : 'h-4 w-4')} />
          </div>
          {!compact && agentName && (
            <span
              className="w-full truncate text-center text-[10px] leading-tight text-muted"
              title={agentName}
            >
              {agentName}
            </span>
          )}
        </div>

        <div className={cn('min-w-0 space-y-1.5', compact ? 'flex-1' : 'max-w-[80%]')}>
          {compact && agentName && (
            <p className="truncate text-[8px] font-medium text-muted" title={agentName}>
              {agentName}
            </p>
          )}
          <AssistantContent message={message} isStreaming={isStreaming} variant={variant} />
          {isStreaming && message.content && message.activity && !compact && (
            <ActivityBubble activity={message.activity} variant={variant} />
          )}
        </div>
      </div>

      {message.tool_calls && message.tool_calls.length > 0 && (
        <div className={cn('space-y-1.5', compact ? 'pl-8' : 'pl-16')}>
          <ToolCallsCollapsible toolCalls={message.tool_calls} variant={variant} />
        </div>
      )}

      {message.sources && message.sources.length > 0 && (
        <div className={cn('space-y-1.5', compact ? 'pl-8' : 'pl-16')}>
          <SourcesCollapsible sources={message.sources} variant={variant} />
        </div>
      )}

      {details}

      {!isStreaming && (
        <div className={cn('space-y-1.5', compact ? 'pl-8' : 'pl-16')}>
          {message.output_parse_error && (
            <div
              className={cn(
                'flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 leading-relaxed text-amber-200',
                compact ? 'px-2 py-1.5 text-[9px]' : 'px-2.5 py-1.5 text-[11px]',
              )}
            >
              <AlertCircle className={cn('mt-0.5 shrink-0', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
              <span>{message.output_parse_error}</span>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <div
              className={cn(
                'flex min-w-0 flex-wrap items-center text-muted',
                compact ? 'gap-x-2 gap-y-1 text-[9px]' : 'gap-3 text-[11px]',
              )}
            >
              {message.model && (
                <span className="break-all">
                  {message.provider ? `${message.provider}/` : ''}{message.model}
                </span>
              )}
              {message.latency_ms != null && <span>{formatLatency(message.latency_ms)}</span>}
              {message.usage && (
                <span>
                  {formatNumber(message.usage.input_tokens, 0)} in / {formatNumber(message.usage.output_tokens, 0)} out
                </span>
              )}
              {message.trace_id && (
                <span className="font-mono">trace {message.trace_id.slice(0, 8)}…</span>
              )}
              {footerMeta}
            </div>

            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => void copyResponse()}
                className={cn(
                  'inline-flex h-6 items-center justify-center gap-1 rounded-md border border-transparent text-muted transition-colors hover:border-border/80 hover:bg-background/70 hover:text-white',
                  compact ? 'px-1.5 text-[9px]' : 'w-6',
                )}
                title={copied ? 'Copied' : 'Copy response'}
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {compact && <span>{copied ? 'Copied' : 'Copy response'}</span>}
              </button>
              {footerActions}
              {!compact && (
                <>
                  <button
                    type="button"
                    className="flex h-6 w-6 items-center justify-center rounded-md border border-transparent text-muted transition-colors hover:border-emerald-500/30 hover:bg-emerald-500/10 hover:text-emerald-300"
                    title="Good response"
                  >
                    <ThumbsUp className="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    className="flex h-6 w-6 items-center justify-center rounded-md border border-transparent text-muted transition-colors hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-300"
                    title="Bad response"
                  >
                    <ThumbsDown className="h-3 w-3" />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
