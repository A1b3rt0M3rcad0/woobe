import { skillActivityLabel } from '@/features/skills/operations'
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
          'flex items-center gap-1 font-mono text-primary-light transition-colors hover:text-white',
          compact ? 'text-[8px]' : 'text-[9px]',
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
                'rounded-container border border-border/80 bg-background/50',
                compact ? 'p-2 text-[9px] leading-4' : 'p-2.5 text-[10px] leading-4',
              )}
            >
              <p className="truncate font-mono text-[9px] font-semibold text-slate-100">{source.document_title || 'Untitled'}</p>
              {(source.page_number != null || source.score != null) && (
                <div className="mt-0.5 flex flex-wrap gap-x-2 font-mono text-[8px] text-muted-foreground">
                  {source.page_number != null && <span>Page {source.page_number}</span>}
                  {source.score != null && <span>Score {formatNumber(source.score, 3)}</span>}
                </div>
              )}
              {source.content_preview && (
                <p className={cn('mt-1 font-sans italic text-muted-foreground', compact ? 'line-clamp-3 text-[9px]' : 'text-[10px]')}>
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
  const skillLabel = activity && skillActivityLabel(activity)
  if (skillLabel) return skillLabel
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
        'inline-flex items-center border border-border/80 bg-surface/65 font-sans text-muted-foreground',
        compact
          ? 'gap-1.5 rounded-control px-2.5 py-2 text-[9px] leading-4'
          : 'gap-2 rounded-container px-3 py-2.5 text-[10px] leading-4',
      )}
    >
      <Loader2 className={cn('animate-spin text-primary-light', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
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
          'border border-border/80 bg-surface/72 font-sans text-slate-100',
          compact
            ? 'rounded-control px-2.5 py-2 text-[10px] leading-4'
            : 'rounded-container px-3 py-2.5 text-[13px] leading-5',
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
        'border border-border/80 bg-surface/72 font-sans text-slate-100',
        compact
          ? 'rounded-control px-2.5 py-2 text-[10px] leading-4'
          : 'rounded-container px-3 py-2.5 text-[13px] leading-5',
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
            className="inline-flex h-3 w-1.5 translate-y-0.5 animate-pulse rounded-technical bg-primary/80"
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
      <div className={cn('flex justify-end overflow-hidden', compact ? 'gap-2' : 'gap-2.5')}>
        <div className={compact ? 'max-w-[88%]' : 'max-w-[80%]'}>
          <div
            className={cn(
              'whitespace-pre-wrap break-words border border-primary/25 bg-primary/[0.09] font-sans text-slate-100',
              compact
                ? 'rounded-control px-2.5 py-2 text-[10px] leading-4'
                : 'rounded-container px-3 py-2.5 text-[13px] leading-5',
            )}
          >
            {message.content}
          </div>
        </div>
        <div
          className={cn(
            'flex shrink-0 items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08]',
            compact ? 'h-6 w-6' : 'h-7 w-7',
          )}
        >
          <User className={cn('text-primary-light', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
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
      <div className={cn('flex justify-start overflow-hidden', compact ? 'gap-2' : 'gap-2.5')}>
        <div className={cn('flex shrink-0 flex-col items-center', compact ? 'w-6 gap-1' : 'w-12 gap-1.5')}>
          <div
            className={cn(
              'flex shrink-0 items-center justify-center rounded-control border border-border bg-control',
              compact ? 'h-6 w-6' : 'h-7 w-7',
            )}
          >
            <AssistantIcon className={cn('text-primary-light', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
          </div>
          {!compact && agentName && (
            <span
              className="w-full truncate text-center font-mono text-[7px] leading-tight text-muted-foreground"
              title={agentName}
            >
              {agentName}
            </span>
          )}
        </div>

        <div className={cn('min-w-0 space-y-1.5', compact ? 'flex-1' : 'max-w-[80%]')}>
          {compact && agentName && (
            <p className="truncate font-mono text-[8px] text-muted-foreground" title={agentName}>
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
        <div className={cn('space-y-1.5', compact ? 'pl-8' : 'pl-[58px]')}>
          <ToolCallsCollapsible toolCalls={message.tool_calls} variant={variant} />
        </div>
      )}

      {message.sources && message.sources.length > 0 && (
        <div className={cn('space-y-1.5', compact ? 'pl-8' : 'pl-[58px]')}>
          <SourcesCollapsible sources={message.sources} variant={variant} />
        </div>
      )}

      {details}

      {!isStreaming && (
        <div className={cn('space-y-1.5', compact ? 'pl-8' : 'pl-[58px]')}>
          {message.output_parse_error && (
            <div
              className={cn(
                'flex items-start gap-1.5 border border-amber-500/25 bg-amber-500/[0.07] leading-relaxed text-amber-200',
                compact ? 'rounded-control px-2 py-1.5 text-[9px]' : 'rounded-container px-2.5 py-1.5 text-[10px]',
              )}
            >
              <AlertCircle className={cn('mt-0.5 shrink-0', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
              <span className="font-sans">{message.output_parse_error}</span>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <div
              className={cn(
                'flex min-w-0 flex-wrap items-center font-mono text-muted-foreground',
                compact ? 'gap-x-2 gap-y-1 text-[8px]' : 'gap-3 text-[8px]',
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
                <span>trace {message.trace_id.slice(0, 8)}…</span>
              )}
              {footerMeta}
            </div>

            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => void copyResponse()}
                className={cn(
                  'inline-flex h-6 items-center justify-center gap-1 rounded-technical border border-transparent font-mono text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50',
                  compact ? 'px-1.5 text-[8px]' : 'w-6',
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
                    className="flex h-6 w-6 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-emerald-500/30 hover:bg-emerald-500/[0.07] hover:text-emerald-300"
                    title="Good response"
                  >
                    <ThumbsUp className="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    className="flex h-6 w-6 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-red-500/30 hover:bg-red-500/[0.07] hover:text-red-300"
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
