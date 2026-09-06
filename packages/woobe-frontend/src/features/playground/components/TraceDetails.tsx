import { operationCountsLabel, operationLabel, operationEventLabel } from '@/features/skills/operations'
import { useState, useRef, useLayoutEffect } from 'react'
import { useTraceDetail } from '@/features/traces/hooks'
import { normalizeTraceDetail } from '@/features/traces/normalizers'
import type { FallbackInfo } from '@/features/traces/types'
import { X, CheckCircle, XCircle, AlertTriangle, HelpCircle, Copy, ChevronDown, ChevronRight, Bug, RefreshCw, Clock, Cpu, Hash, FileText, Brain } from 'lucide-react'
import { formatLatency, formatTokens, formatCurrency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { TraceItem } from '@/features/playground/types'
import type { TraceDetailNormalized, TraceEvent } from '@/features/traces/types'

interface TraceDetailsProps {
  trace: TraceItem
  onBack: () => void
}

function ClampedText({ text, lines = 2 }: { text: string; lines?: number }) {
  const ref = useRef<HTMLParagraphElement>(null)
  const [expanded, setExpanded] = useState(false)
  const [overflows, setOverflows] = useState(false)

  useLayoutEffect(() => {
    const el = ref.current
    if (el) {
      setOverflows(el.scrollHeight > el.clientHeight)
    }
  }, [text, expanded])

  return (
    <div className="relative">
      <p
        ref={ref}
        className={`text-xs text-white whitespace-pre-wrap break-words leading-relaxed ${expanded ? '' : `line-clamp-${lines}`}`}
      >
        {text}
      </p>
      {overflows && !expanded && (
        <div className="absolute bottom-0 inset-x-0 h-6 bg-gradient-to-t from-surface to-transparent pointer-events-none" />
      )}
      {overflows && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-blue-400 hover:text-blue-300 mt-0.5"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  )
}

function CopyableIdRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const truncated = value.length > 12 ? `${value.slice(0, 8)}…` : value

  return (
    <div className="grid grid-cols-[60px_1fr_20px] items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5">
      <span className="text-[10px] text-muted uppercase leading-none">{label}</span>
      <code className="text-[11px] text-white font-mono truncate">{truncated}</code>
      <button
        onClick={handleCopy}
        className="text-muted hover:text-white transition-colors justify-self-end"
        title={copied ? 'Copied!' : 'Copy'}
      >
        <Copy className="h-3 w-3" />
      </button>
    </div>
  )
}

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
  badge,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
  badge?: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full py-1.5 text-xs font-medium text-muted hover:text-white transition-colors group"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <span className="group-hover:text-white transition-colors">{title}</span>
        {badge && <span className="text-[10px] text-muted ml-auto">{badge}</span>}
      </button>
      {open && <div className="pb-2">{children}</div>}
    </div>
  )
}

function UsageInline({
  inputTokens,
  outputTokens,
  totalTokens,
  costUsd,
}: {
  inputTokens?: number | null
  outputTokens?: number | null
  totalTokens?: number | null
  costUsd?: number | null
}) {
  const parts: string[] = []
  if (inputTokens != null) parts.push(`Input ${formatTokens(inputTokens)}`)
  if (outputTokens != null) parts.push(`Output ${formatTokens(outputTokens)}`)
  if (totalTokens != null) parts.push(`Total ${formatTokens(totalTokens)}`)
  if (costUsd != null) parts.push(formatCurrency(costUsd))
  if (parts.length === 0) return null
  return <p className="text-[11px] text-muted">{parts.join('  ·  ')}</p>
}

const statusConfig: Record<string, { label: string; className: string; icon: typeof CheckCircle }> = {
  completed: { label: 'Completed', className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', icon: CheckCircle },
  success: { label: 'Completed', className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', icon: CheckCircle },
  running: { label: 'Running', className: 'bg-blue-500/10 text-blue-400 border-blue-500/20', icon: AlertTriangle },
  processing: { label: 'Processing', className: 'bg-blue-500/10 text-blue-400 border-blue-500/20', icon: AlertTriangle },
  warning: { label: 'Warning', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', icon: AlertTriangle },
  failed: { label: 'Failed', className: 'bg-red-500/10 text-red-400 border-red-500/20', icon: XCircle },
  error: { label: 'Failed', className: 'bg-red-500/10 text-red-400 border-red-500/20', icon: XCircle },
  pending: { label: 'Queued', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', icon: HelpCircle },
  queued: { label: 'Queued', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', icon: HelpCircle },
  cancelled: { label: 'Cancelled', className: 'bg-gray-500/10 text-gray-400 border-gray-500/20', icon: XCircle },
}

function StatusBadge({ status, latencyMs, model, provider, fallbackUsed }: {
  status: string
  latencyMs?: number | null
  model?: string | null
  provider?: string | null
  fallbackUsed?: boolean
}) {
  const cfg = statusConfig[status] || statusConfig.completed
  const Icon = cfg.icon
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border', cfg.className)}>
        <Icon className="h-3 w-3" />
        {cfg.label}
      </span>
      {latencyMs != null && (
        <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] text-muted font-mono bg-background border border-border">
          {formatLatency(latencyMs)}
        </span>
      )}
      {(provider || model) && (
        <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] text-muted font-mono bg-background border border-border">
          {provider || '—'}/{model || '—'}
        </span>
      )}
      {fallbackUsed && (
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
          <AlertTriangle className="h-3 w-3" />
          Fallback
        </span>
      )}
    </div>
  )
}

function SourceBadge(source: { document_title?: string | null }): string {
  const title = source.document_title ?? ''
  if (title.endsWith('.pdf')) return 'PDF'
  if (title.endsWith('.md') || title.endsWith('.txt') || title.endsWith('.doc')) return 'DOC'
  if (title.includes('http://') || title.includes('https://')) return 'URL'
  return 'DB'
}

function SourceList({ sources }: { sources: { document_title?: string | null; score?: number | null }[] }) {
  return (
    <div className="space-y-1">
      {sources.map((source, idx) => (
        <div key={idx} className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
          <span className={cn(
            'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase',
            SourceBadge(source) === 'DB' ? 'bg-violet-500/10 text-violet-400' :
            SourceBadge(source) === 'DOC' ? 'bg-blue-500/10 text-blue-400' :
            SourceBadge(source) === 'PDF' ? 'bg-orange-500/10 text-orange-400' :
            'bg-cyan-500/10 text-cyan-400',
          )}>
            {SourceBadge(source)}
          </span>
          <span className="text-xs text-muted flex-1 truncate">
            {source.document_title || `Source ${idx + 1}`}
          </span>
          {source.score != null && (
            <span className="text-[11px] text-muted font-mono">
              {(source.score * 100).toFixed(0)}%
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

function ToolCallList({ toolCalls }: { toolCalls: { tool_name: string; status?: string | null; duration_ms?: number | null; latency_ms?: number | null }[] }) {
  return (
    <div className="space-y-1">
      {toolCalls.map((tc, idx) => (
        <div key={idx} className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
          {tc.status === 'success' ? (
            <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
          ) : tc.status === 'failed' || tc.status === 'error' ? (
            <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
          ) : (
            <HelpCircle className="h-3.5 w-3.5 text-muted shrink-0" />
          )}
          <span className="text-xs text-white flex-1 truncate">{operationLabel(tc)}</span>
          {tc.status && (
            <span className={cn(
              'text-[10px] font-medium',
              tc.status === 'success' ? 'text-emerald-400' :
              tc.status === 'failed' || tc.status === 'error' ? 'text-red-400' :
              'text-muted',
            )}>
              {tc.status.charAt(0).toUpperCase() + tc.status.slice(1)}
            </span>
          )}
          {(tc.duration_ms || tc.latency_ms) && (
            <span className="text-[11px] text-muted font-mono">
              {formatLatency(tc.duration_ms ?? tc.latency_ms)}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

function EventTimeline({ events }: { events: TraceEvent[] }) {
  return (
    <div className="space-y-1">
      {events.map((evt) => (
        <div key={evt.id} className="rounded-lg border border-border bg-background px-3 py-2">
          <div className="flex items-center justify-between">
            <code className="text-[11px] text-white font-mono">{operationEventLabel(evt.event_type, evt.payload)}</code>
            <span className="text-[10px] text-muted">{evt.created_at ? new Date(evt.created_at).toLocaleTimeString() : ''}</span>
          </div>
          {evt.payload && <JsonCodeBlock value={evt.payload} maxHeight={96} className="mt-1" />}
        </div>
      ))}
    </div>
  )
}

function DetailView({ traceId, projectId, agentId, sessionId, messageId, status, model, provider, latencyMs, usage, sources, toolCalls, parsedOutput, outputParseError, events, fallbackInfo }: {
  traceId: string
  projectId?: string | null
  agentId?: string | null
  sessionId?: string | null
  messageId?: string | null
  status: string
  model?: string | null
  provider?: string | null
  latencyMs?: number | null
  usage?: { inputTokens?: number | null; outputTokens?: number | null; totalTokens?: number | null; costUsd?: number | null } | null
  sources?: { document_title?: string | null; score?: number | null }[]
  toolCalls?: { tool_name: string; status?: string | null; duration_ms?: number | null; latency_ms?: number | null }[]
  parsedOutput?: unknown
  outputParseError?: string | null
  events?: TraceEvent[]
  fallbackInfo?: FallbackInfo | null
}) {
  const userEvent = events?.find(e => e.event_type === 'ask.started')
  const userMessage = userEvent?.payload?.message as string | undefined
  const completedEvent = events?.find(e => e.event_type === 'ask.completed')
  const answerLength = completedEvent?.payload?.answer_length as number | undefined

  const hasDetailSections = !!(
    (sources?.length ?? 0) > 0 ||
    (toolCalls?.length ?? 0) > 0 ||
    parsedOutput ||
    outputParseError ||
    (events?.length ?? 0) > 0
  )

  return (
    <div className="space-y-3 p-4">
      <StatusBadge status={status} latencyMs={latencyMs} model={model} provider={provider} fallbackUsed={!!fallbackInfo} />

      <UsageInline
        inputTokens={usage?.inputTokens}
        outputTokens={usage?.outputTokens}
        totalTokens={usage?.totalTokens}
        costUsd={usage?.costUsd}
      />

      {outputParseError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span className="text-xs font-medium text-red-400">Output Parse Error</span>
          </div>
          <p className="text-xs text-muted break-all">{outputParseError}</p>
        </div>
      )}

      {fallbackInfo && (
        <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-2.5 space-y-1">
          <p className="text-[10px] font-medium text-yellow-400 uppercase tracking-wider">Fallback Details</p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
            <span className="text-muted">Primary:</span>
            <span className="text-white font-mono text-right truncate">{fallbackInfo.primary_provider}/{fallbackInfo.primary_model}</span>
            <span className="text-muted">Fallback:</span>
            <span className="text-white font-mono text-right truncate">{fallbackInfo.fallback_provider}/{fallbackInfo.fallback_model}</span>
            <span className="text-muted col-span-2">Error:</span>
            <span className="text-red-400 font-mono text-[10px] col-span-2 break-all">{fallbackInfo.primary_error}</span>
          </div>
        </div>
      )}

      {userMessage && (
        <div className="rounded-lg border border-border bg-background p-2.5">
          <p className="text-[10px] font-medium text-muted uppercase tracking-wider mb-1">User Message</p>
          <ClampedText text={userMessage} lines={2} />
        </div>
      )}

      {answerLength != null && (
        <div className="rounded-lg border border-border bg-background p-2.5">
          <p className="text-[10px] font-medium text-muted uppercase tracking-wider mb-1">Response</p>
          <p className="text-xs text-muted">{formatTokens(answerLength)} characters (stored in session messages)</p>
        </div>
      )}

      {hasDetailSections && (
        <div className="border-t border-border pt-1.5 space-y-0.5">
          {sources && sources.length > 0 && (
            <CollapsibleSection title="Sources" badge={`${sources.length}`}>
              <SourceList sources={sources} />
            </CollapsibleSection>
          )}
          {toolCalls && toolCalls.length > 0 && (
            <CollapsibleSection title={operationCountsLabel(toolCalls)}>
              <ToolCallList toolCalls={toolCalls} />
            </CollapsibleSection>
          )}
          {!!parsedOutput && !outputParseError && (
            <CollapsibleSection title="Structured Output">
              <JsonCodeBlock value={parsedOutput} maxHeight={128} />
            </CollapsibleSection>
          )}
          {events && events.length > 0 && (
            <CollapsibleSection title="Events" badge={`${events.length}`}>
              <EventTimeline events={events} />
            </CollapsibleSection>
          )}
          <CollapsibleSection title="Raw">
            <JsonCodeBlock value={{ status, model, provider, latencyMs, usage, sources, toolCalls, parsedOutput, events }} maxHeight={128} />
          </CollapsibleSection>
        </div>
      )}

      <div className="border-t border-border pt-1.5 space-y-1">
        <CopyableIdRow label="trace" value={traceId} />
        {sessionId && <CopyableIdRow label="session" value={sessionId} />}
        {messageId && <CopyableIdRow label="message" value={messageId} />}
        {projectId && <CopyableIdRow label="project" value={projectId} />}
        {agentId && <CopyableIdRow label="agent" value={agentId} />}
      </div>
    </div>
  )
}

function BackendTraceDetail({ traceId, onBack }: { traceId: string; onBack: () => void }) {
  const { data: rawDetail, isLoading, isError, error, refetch } = useTraceDetail(traceId)

  const detail = rawDetail ? normalizeTraceDetail(rawDetail) : null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-4 pt-4">
        <h3 className="text-sm font-medium text-white">Trace Detail</h3>
        <button
          onClick={onBack}
          className="rounded-lg p-1 text-muted hover:text-white hover:bg-accent transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {isLoading && (
        <div className="p-4 text-center">
          <RefreshCw className="h-5 w-5 animate-spin text-muted mx-auto mb-2" />
          <p className="text-sm text-muted">Loading trace details...</p>
        </div>
      )}

      {isError && (
        <div className="p-4 text-center">
          <AlertTriangle className="h-5 w-5 text-red-400 mx-auto mb-2" />
          <p className="text-sm text-red-400">Failed to load trace details</p>
          {error instanceof Error && <p className="text-xs text-muted mt-1">{error.message}</p>}
          <button
            onClick={() => refetch()}
            className="mt-3 text-xs text-primary hover:underline inline-flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      )}

      {detail && (
        <DetailView
          traceId={traceId}
          projectId={detail.projectId}
          agentId={detail.agentId}
          sessionId={detail.sessionId}
          messageId={detail.messageId}
          status={detail.status}
          model={detail.model}
          provider={detail.provider}
          latencyMs={detail.latencyMs}
          usage={detail.usage}
          sources={detail.sources}
          toolCalls={detail.toolCalls}
          parsedOutput={detail.parsedOutput}
          outputParseError={detail.outputParseError}
          events={detail.events}
          fallbackInfo={detail.fallbackInfo}
        />
      )}
    </div>
  )
}

function LocalTraceDetail({ trace, onBack }: { trace: TraceItem; onBack: () => void }) {
  const response = trace.response!
  const hasDetailSections = !!(
    (response.sources?.length ?? 0) > 0 ||
    (response.tool_calls?.length ?? 0) > 0 ||
    response.parsed_output ||
    trace.trace_id
  )

  if (response.output_parse_error) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between px-4 pt-4">
          <h3 className="text-sm font-medium text-white">Trace Detail</h3>
          <button onClick={onBack} className="rounded-lg p-1 text-muted hover:text-white hover:bg-accent transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-4 space-y-2">
          <StatusBadge status={trace.status} latencyMs={trace.latency_ms} model={trace.model} provider={trace.provider} fallbackUsed={trace.fallback_used} />
          <UsageInline inputTokens={trace.input_tokens} outputTokens={trace.output_tokens} totalTokens={trace.total_tokens} costUsd={trace.cost_usd} />
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 space-y-2">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-400 shrink-0" />
              <span className="text-xs font-medium text-red-400">Parse Error</span>
            </div>
            <p className="text-xs text-muted break-all">{response.output_parse_error}</p>
          </div>
          <CollapsibleSection title="Raw">
            <JsonCodeBlock value={response} maxHeight={128} />
          </CollapsibleSection>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-4 pt-4">
        <h3 className="text-sm font-medium text-white">Trace Detail</h3>
        <button onClick={onBack} className="rounded-lg p-1 text-muted hover:text-white hover:bg-accent transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="px-4 space-y-3">
        <StatusBadge status={trace.status} latencyMs={trace.latency_ms} model={trace.model} provider={trace.provider} fallbackUsed={trace.fallback_used} />
        <UsageInline inputTokens={trace.input_tokens} outputTokens={trace.output_tokens} totalTokens={trace.total_tokens} costUsd={trace.cost_usd} />

        {trace.fallback_used && trace.fallback_info && (
          <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-2.5 space-y-1">
            <p className="text-[10px] font-medium text-yellow-400 uppercase tracking-wider">Fallback Details</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
              <span className="text-muted">Primary:</span>
              <span className="text-white font-mono text-right truncate">{trace.fallback_info.primary_provider}/{trace.fallback_info.primary_model}</span>
              <span className="text-muted">Fallback:</span>
              <span className="text-white font-mono text-right truncate">{trace.fallback_info.fallback_provider}/{trace.fallback_info.fallback_model}</span>
              <span className="text-muted col-span-2">Error:</span>
              <span className="text-red-400 font-mono text-[10px] col-span-2 break-all">{trace.fallback_info.primary_error}</span>
            </div>
          </div>
        )}

        {response.answer && (
          <div className="rounded-lg border border-border bg-background p-2.5">
            <p className="text-[10px] font-medium text-muted uppercase tracking-wider mb-1">Answer</p>
            <ClampedText text={response.answer} lines={2} />
          </div>
        )}

        {hasDetailSections && (
          <div className="border-t border-border pt-1.5 space-y-0.5">
            {response.sources && response.sources.length > 0 && (
              <CollapsibleSection title="Sources" badge={`${response.sources.length}`}>
                <SourceList sources={response.sources} />
              </CollapsibleSection>
            )}
            {response.tool_calls && response.tool_calls.length > 0 && (
              <CollapsibleSection title={operationCountsLabel(response.tool_calls)}>
                <ToolCallList toolCalls={response.tool_calls} />
              </CollapsibleSection>
            )}
            {response.parsed_output && (
              <CollapsibleSection title="Structured Output">
                <JsonCodeBlock value={response.parsed_output} maxHeight={128} />
              </CollapsibleSection>
            )}
            <CollapsibleSection title="Raw">
<JsonCodeBlock value={response} maxHeight={128} />
            </CollapsibleSection>
          </div>
        )}

        {trace.trace_id && (
          <div className="border-t border-border pt-1.5 space-y-1">
            <CopyableIdRow label="trace" value={trace.trace_id} />
            {response.session_id && <CopyableIdRow label="session" value={response.session_id} />}
            {response.message_id && <CopyableIdRow label="message" value={response.message_id} />}
            {trace.project_id && <CopyableIdRow label="project" value={trace.project_id} />}
            {trace.agent_id && <CopyableIdRow label="agent" value={trace.agent_id} />}
          </div>
        )}
      </div>
    </div>
  )
}

export function TraceDetails({ trace, onBack }: TraceDetailsProps) {
  if (trace.response) {
    return <LocalTraceDetail trace={trace} onBack={onBack} />
  }

  const backendId = trace.trace_id || trace.id
  if (backendId && !backendId.startsWith('trace-')) {
    return <BackendTraceDetail traceId={backendId} onBack={onBack} />
  }

  return (
    <div className="p-4 text-center">
      <Bug className="h-8 w-8 text-muted mx-auto mb-2 opacity-40" />
      <p className="text-sm text-muted">No trace data available</p>
    </div>
  )
}
