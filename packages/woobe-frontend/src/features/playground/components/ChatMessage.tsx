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
import { Button, woobeLayout } from '@woobe/ui'

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
    <div className={compact ? 'mt-ui-xs' : 'mt-ui-sm'}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-ui-xs font-mono text-primary-light transition-colors hover:text-slate-50',
          compact ? 'text-system-meta' : 'text-system-label',
        )}
      >
        {open ? <ChevronDown className="h-icon-sm w-icon-sm" /> : <ChevronRight className="h-icon-sm w-icon-sm" />}
        Sources ({sources.length})
      </button>
      {open && (
        <div className={cn('mt-ui-xs space-y-ui-xs', compact && 'max-w-full')}>
          {sources.map((source, index) => (
            <div
              key={source.chunk_id || `${source.document_id || 'source'}-${index}`}
              className={cn(
                'rounded-container border border-border/80 bg-background/50',
                compact ? 'p-ui-sm' : 'p-ui-md',
              )}
            >
              <p className="truncate font-mono text-system-label font-semibold text-slate-100">{source.document_title || 'Untitled'}</p>
              {(source.page_number != null || source.score != null) && (
                <div className="mt-ui-xs flex flex-wrap gap-x-ui-sm font-mono text-system-meta text-muted-foreground">
                  {source.page_number != null && <span>Page {source.page_number}</span>}
                  {source.score != null && <span>Score {formatNumber(source.score, 3)}</span>}
                </div>
              )}
              {source.content_preview && (
                <p className={cn('mt-ui-xs font-sans italic text-muted-foreground', compact ? 'line-clamp-3 text-product-caption' : 'text-product-small')}>
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
          ? 'gap-ui-sm rounded-control px-ui-sm py-ui-sm text-product-caption'
          : 'gap-ui-sm rounded-container px-ui-md py-ui-sm text-product-small',
      )}
    >
      <Loader2 className={cn('animate-spin text-primary-light', compact ? 'h-icon-sm w-icon-sm' : 'h-icon w-icon')} />
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
            ? 'rounded-control px-ui-sm py-ui-sm text-product-small'
            : 'rounded-container px-ui-md py-ui-sm text-product-body',
        )}
      >
        <MarkdownMessage
          content={segments[0].content}
          isStreaming={isStreaming}
          className={compact ? 'space-y-ui-sm text-product-small' : undefined}
        />
      </div>
    )
  }

  return (
    <div
      className={cn(
        'border border-border/80 bg-surface/72 font-sans text-slate-100',
        compact
          ? 'rounded-control px-ui-sm py-ui-sm text-product-small'
          : 'rounded-container px-ui-md py-ui-sm text-product-body',
      )}
    >
      <div className={compact ? 'space-y-ui-sm' : 'space-y-ui-md'}>
        {segments.map((segment, index) =>
          segment.type === 'text' ? (
            <MarkdownMessage
              key={index}
              content={segment.content}
              className={compact ? 'space-y-ui-sm text-product-small' : undefined}
            />
          ) : (
            <div key={index} className={compact ? 'my-ui-sm' : 'my-ui-md'}>
              <JsonCodeBlock value={segment.value} maxHeight={compact ? woobeLayout.codeInlineCompact : woobeLayout.codeInlineDefault} />
            </div>
          ),
        )}
        {isStreaming && (
          <span
            className="inline-flex h-icon-sm w-1.5 translate-y-0.5 animate-pulse rounded-technical bg-primary/80"
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
      <div className={cn('flex justify-end overflow-hidden', compact ? 'gap-ui-sm' : 'gap-ui-md')}>
        <div className={compact ? 'max-w-conversation-compact' : 'max-w-conversation'}>
          <div
            className={cn(
              'whitespace-pre-wrap break-words border border-primary/25 bg-primary/[0.09] font-sans text-slate-100',
              compact
                ? 'rounded-control px-ui-sm py-ui-sm text-product-small'
                : 'rounded-container px-ui-md py-ui-sm text-product-body',
            )}
          >
            {message.content}
          </div>
        </div>
        <div
          className={cn(
            'flex shrink-0 items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08]',
            compact ? 'h-control-xs w-control-xs' : 'h-control-segment w-control-segment',
          )}
        >
          <User className={cn('text-primary-light', compact ? 'h-icon-sm w-icon-sm' : 'h-icon w-icon')} />
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
    <div className={cn('flex flex-col', compact ? 'gap-ui-xs' : 'gap-ui-sm')}>
      <div className={cn('flex justify-start overflow-hidden', compact ? 'gap-ui-sm' : 'gap-ui-md')}>
        <div className={cn('flex shrink-0 flex-col items-center', compact ? 'w-conversation-rail-compact gap-ui-xs' : 'w-conversation-rail gap-ui-sm')}>
          <div
            className={cn(
              'flex shrink-0 items-center justify-center rounded-control border border-border bg-control',
              compact ? 'h-control-xs w-control-xs' : 'h-control-segment w-control-segment',
            )}
          >
            <AssistantIcon className={cn('text-primary-light', compact ? 'h-icon-sm w-icon-sm' : 'h-icon w-icon')} />
          </div>
          {!compact && agentName && (
            <span className="w-full truncate text-center font-mono text-system-meta text-muted-foreground" title={agentName}>
              {agentName}
            </span>
          )}
        </div>

        <div className={cn('min-w-0 space-y-ui-sm', compact ? 'flex-1' : 'max-w-conversation')}>
          {compact && agentName && (
            <p className="truncate font-mono text-system-meta text-muted-foreground" title={agentName}>
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
        <div className={cn('space-y-ui-sm', compact ? 'pl-conversation-indent-compact' : 'pl-conversation-indent')}>
          <ToolCallsCollapsible toolCalls={message.tool_calls} variant={variant} />
        </div>
      )}

      {message.sources && message.sources.length > 0 && (
        <div className={cn('space-y-ui-sm', compact ? 'pl-conversation-indent-compact' : 'pl-conversation-indent')}>
          <SourcesCollapsible sources={message.sources} variant={variant} />
        </div>
      )}

      {details}

      {!isStreaming && (
        <div className={cn('space-y-ui-sm', compact ? 'pl-conversation-indent-compact' : 'pl-conversation-indent')}>
          {message.output_parse_error && (
            <div
              className={cn(
                'flex items-start gap-ui-sm border border-amber-500/25 bg-amber-500/[0.07] text-amber-200',
                compact ? 'rounded-control px-ui-sm py-ui-xs font-sans text-product-caption' : 'rounded-container px-ui-sm py-ui-sm font-sans text-product-small',
              )}
            >
              <AlertCircle className={cn('mt-ui-hairline shrink-0', compact ? 'h-icon-sm w-icon-sm' : 'h-icon w-icon')} />
              <span>{message.output_parse_error}</span>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-x-ui-md gap-y-ui-xs">
            <div className={cn('flex min-w-0 flex-wrap items-center font-mono text-system-meta text-muted-foreground', compact ? 'gap-x-ui-sm gap-y-ui-xs' : 'gap-ui-md')}>
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

            <div className="flex shrink-0 items-center gap-ui-xs">
              <Button
                type="button"
                variant="ghost"
                size={compact ? 'xs' : 'iconXs'}
                onClick={() => void copyResponse()}
                className="text-muted-foreground"
                title={copied ? 'Copied' : 'Copy response'}
              >
                {copied ? <Check className="h-icon-sm w-icon-sm" /> : <Copy className="h-icon-sm w-icon-sm" />}
                {compact && <span>{copied ? 'Copied' : 'Copy response'}</span>}
              </Button>
              {footerActions}
              {!compact && (
                <>
                  <Button type="button" variant="ghost" size="iconXs" className="text-muted-foreground hover:border-emerald-500/30 hover:bg-emerald-500/[0.07] hover:text-emerald-300" title="Good response">
                    <ThumbsUp className="h-icon-sm w-icon-sm" />
                  </Button>
                  <Button type="button" variant="ghost" size="iconXs" className="text-muted-foreground hover:border-red-500/30 hover:bg-red-500/[0.07] hover:text-red-300" title="Bad response">
                    <ThumbsDown className="h-icon-sm w-icon-sm" />
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
