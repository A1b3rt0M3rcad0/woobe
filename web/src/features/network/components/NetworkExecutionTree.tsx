import { useState } from 'react'
import { Bot, CheckCircle2, ChevronDown, ChevronRight, CircleDot, Loader2, Workflow, XCircle } from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { MarkdownMessage } from '@/features/playground/components/MarkdownMessage'
import { StructuredJsonResponse } from '@/features/playground/components/StructuredJsonResponse'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import type { SourceInfo } from '@/features/playground/types'
import { formatLatency, formatNumber } from '@/lib/formatters/number'
import { parseAssistantMessageContent } from '@/lib/parse-assistant-message'
import { cn } from '@/lib/utils'

import type { AgentNodeId } from './networkWorkspaceTypes'
import { invocationCount, invocationPath, sourceCount, toolCount, type AgentInvocationStatus, type NetworkAgentInvocation, type NetworkExecution, type NetworkTurn } from './networkChatExecution'

const sourceTone: Record<NetworkAgentInvocation['source'], string> = {
  draft: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
  release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
}

function RichMessageContent({
  content,
  parsedOutput,
  compact = false,
}: {
  content: string
  parsedOutput?: Record<string, unknown> | null
  compact?: boolean
}) {
  if (parsedOutput) {
    return <StructuredJsonResponse value={parsedOutput} density={compact ? 'compact' : 'comfortable'} />
  }

  const parsed = parseAssistantMessageContent(content)
  if (parsed.isPureJson && parsed.segments[0]?.type === 'json') {
    return <StructuredJsonResponse value={parsed.segments[0].value} raw={parsed.segments[0].raw} density={compact ? 'compact' : 'comfortable'} />
  }

  if (parsed.segments.length === 1 && parsed.segments[0]?.type === 'text') {
    return <MarkdownMessage content={parsed.segments[0].content} />
  }

  return (
    <div className="space-y-3">
      {parsed.segments.map((segment, index) => segment.type === 'text' ? (
        <MarkdownMessage key={`${segment.type}-${index}`} content={segment.content} />
      ) : (
        <JsonCodeBlock key={`${segment.type}-${index}`} value={segment.value} maxHeight={compact ? 150 : 220} />
      ))}
    </div>
  )
}

function SourcesSection({ sources }: { sources: SourceInfo[] }) {
  const [open, setOpen] = useState(false)
  if (!sources.length) return null

  return (
    <div className="rounded-lg border border-border/70 bg-background/35">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[10px] text-primary-light hover:text-white"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span className="font-medium">Sources</span>
        <span className="text-muted">{sources.length}</span>
      </button>
      {open ? (
        <div className="space-y-2 border-t border-border/70 p-2.5">
          {sources.map((source, index) => (
            <article key={source.chunk_id || `${source.document_id || 'source'}-${index}`} className="rounded-lg border border-border/70 bg-surface/45 p-2.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p className="min-w-0 flex-1 truncate text-[10px] font-medium text-white">{source.document_title || 'Untitled document'}</p>
                {source.page_number != null ? <span className="text-[9px] text-muted">Page {source.page_number}</span> : null}
                {source.score != null ? <span className="text-[9px] text-muted">Score {formatNumber(source.score, 3)}</span> : null}
              </div>
              {source.content_preview ? <p className="mt-1.5 line-clamp-3 text-[9px] leading-4 text-muted">“{source.content_preview}”</p> : null}
            </article>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function statusIcon(status: AgentInvocationStatus) {
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />
  if (status === 'error') return <XCircle className="h-3.5 w-3.5 text-red-400" />
  if (status === 'success') return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
  return <CircleDot className="h-3.5 w-3.5 text-muted" />
}

function AgentInvocationNode({
  invocation,
  depth,
  onSelectAgent,
}: {
  invocation: NetworkAgentInvocation
  depth: number
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  const [open, setOpen] = useState(depth === 0 || invocation.status === 'error')
  const hasDetails = Boolean(
    invocation.output
    || invocation.parsedOutput
    || invocation.outputParseError
    || invocation.tools.length
    || invocation.sources.length
    || invocation.children.length,
  )

  return (
    <div className={cn(depth > 0 && 'border-l border-border/80 pl-3')}>
      <article className={cn(
        'overflow-hidden rounded-xl border bg-background/35',
        invocation.status === 'error' ? 'border-red-500/30' : 'border-border/80',
      )}>
        <button
          type="button"
          onClick={() => hasDetails && setOpen((value) => !value)}
          className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left"
        >
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
            {statusIcon(invocation.status)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              {invocation.nodeId ? (
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelectAgent(invocation.nodeId!)
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      event.stopPropagation()
                      onSelectAgent(invocation.nodeId!)
                    }
                  }}
                  className="truncate text-[11px] font-semibold text-white hover:text-primary-light"
                >
                  {invocation.agentName}
                </span>
              ) : (
                <span className="truncate text-[11px] font-semibold text-white">{invocation.agentName}</span>
              )}
              <span className={cn('rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceTone[invocation.source])}>
                {invocation.source}
              </span>
              <span className="truncate font-mono text-[8px] text-muted">{invocation.version}</span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-muted">
              {invocation.provider || invocation.model ? <span>{invocation.provider || '—'}/{invocation.model || '—'}</span> : null}
              {invocation.durationMs != null ? <span>{formatLatency(invocation.durationMs)}</span> : null}
              {invocation.usage ? <span>{formatNumber(invocation.usage.input_tokens, 0)} in / {formatNumber(invocation.usage.output_tokens, 0)} out</span> : null}
              {invocation.costUsd != null ? <span>${invocation.costUsd.toFixed(3)}</span> : null}
            </div>
          </div>
          {hasDetails ? (open ? <ChevronDown className="mt-1 h-3.5 w-3.5 shrink-0 text-muted" /> : <ChevronRight className="mt-1 h-3.5 w-3.5 shrink-0 text-muted" />) : null}
        </button>

        {open ? (
          <div className="space-y-2.5 border-t border-border/70 px-3 py-3">
            {invocation.output || invocation.parsedOutput ? (
              <div className="rounded-lg border border-border/70 bg-surface/55 p-3 text-[10px] leading-5 text-slate-200">
                <RichMessageContent content={invocation.output || ''} parsedOutput={invocation.parsedOutput} compact />
              </div>
            ) : null}
            {invocation.outputParseError ? (
              <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[9px] text-amber-200">
                {invocation.outputParseError}
              </div>
            ) : null}
            {invocation.tools.length ? <ToolCallsCollapsible toolCalls={invocation.tools} variant="network" /> : null}
            <SourcesSection sources={invocation.sources} />
            {invocation.children.length ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-[9px] font-medium uppercase tracking-wide text-muted">
                  <Bot className="h-3 w-3" />
                  Agents called ({invocation.children.length})
                </div>
                <div className="space-y-2">
                  {invocation.children.map((child) => (
                    <AgentInvocationNode
                      key={child.spanId}
                      invocation={child}
                      depth={Math.min(depth + 1, 3)}
                      onSelectAgent={onSelectAgent}
                    />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </article>
    </div>
  )
}

function NetworkExecutionSummary({
  execution,
  onOpenTrace,
  onSelectAgent,
}: {
  execution: NetworkExecution
  onOpenTrace: (execution: NetworkExecution) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  const [open, setOpen] = useState(false)
  const agents = invocationCount(execution.root)
  const tools = toolCount(execution.root)
  const sources = sourceCount(execution.root)
  const path = ['ENTRY', ...invocationPath(execution.root), 'END'].join(' → ')

  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-background/35">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
        <span className="text-[10px] font-medium text-white">Execution completed</span>
        <span className="text-[9px] text-muted">{agents} Agents · {tools} {tools === 1 ? 'Tool' : 'Tools'} · {sources} Sources</span>
        <span className="ml-auto text-[9px] text-muted">{formatLatency(execution.durationMs)} · ${execution.costUsd.toFixed(3)}</span>
      </div>
      <div className="border-t border-border/70 px-3 py-2">
        <p className="truncate text-[9px] text-primary-light" title={path}>{path}</p>
        <div className="mt-2 flex items-center gap-3">
          <button type="button" onClick={() => setOpen((value) => !value)} className="text-[9px] font-medium text-primary-light hover:text-white">
            {open ? 'Hide execution' : 'View execution'}
          </button>
          <button type="button" onClick={() => onOpenTrace(execution)} className="text-[9px] text-muted hover:text-white">Open trace</button>
          <span className="ml-auto font-mono text-[8px] text-muted">trace {execution.traceId.slice(0, 8)}…</span>
        </div>
      </div>
      {open ? (
        <div className="border-t border-border/70 p-3">
          <AgentInvocationNode invocation={execution.root} depth={0} onSelectAgent={onSelectAgent} />
        </div>
      ) : null}
    </div>
  )
}

export function NetworkAnswer({
  networkName,
  turn,
  onOpenTrace,
  onSelectAgent,
}: {
  networkName: string
  turn: NetworkTurn
  onOpenTrace: (execution: NetworkExecution) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  return (
    <div className="space-y-2.5">
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10">
          <Workflow className="h-4 w-4 text-primary-light" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="mb-1.5 truncate text-[10px] font-medium text-muted">{networkName}</p>
          <div className="rounded-xl rounded-bl-md border border-border/80 bg-surface/75 px-4 py-3 text-[12px] leading-5 text-white shadow-sm shadow-black/5">
            <RichMessageContent content={turn.answer} parsedOutput={turn.parsedOutput} />
          </div>
          {turn.outputParseError ? (
            <div className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[9px] text-amber-200">
              {turn.outputParseError}
            </div>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-muted">
            <span>{turn.provider}/{turn.model}</span>
            <span>{formatLatency(turn.execution.durationMs)}</span>
            <span>{formatNumber(turn.usage.input_tokens, 0)} in / {formatNumber(turn.usage.output_tokens, 0)} out</span>
            <span>${turn.execution.costUsd.toFixed(3)}</span>
          </div>
        </div>
      </div>
      <div className="pl-11">
        <NetworkExecutionSummary execution={turn.execution} onOpenTrace={onOpenTrace} onSelectAgent={onSelectAgent} />
      </div>
    </div>
  )
}
