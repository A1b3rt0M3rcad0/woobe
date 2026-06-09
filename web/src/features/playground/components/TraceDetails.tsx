import { MetricCard } from './MetricCard'
import { JsonCodeBlock } from './JsonCodeBlock'
import { CopyButton } from '@/components/common/CopyButton'
import { X, Clock, Cpu, FileText, Hash, Brain, Database, FileText as FileIcon, Globe, CheckCircle, XCircle, HelpCircle } from 'lucide-react'
import { formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'
import type { TraceItem } from '@/features/playground/types'

interface TraceDetailsProps {
  trace: TraceItem
  onBack: () => void
}

const statusBadge: Record<string, { label: string; className: string }> = {
  completed: { label: 'Completed', className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  success: { label: 'Completed', className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  running: { label: 'Running', className: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  processing: { label: 'Processing', className: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  failed: { label: 'Failed', className: 'bg-red-500/10 text-red-400 border-red-500/20' },
  error: { label: 'Failed', className: 'bg-red-500/10 text-red-400 border-red-500/20' },
  pending: { label: 'Queued', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  queued: { label: 'Queued', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
}

function sourceBadge(source: { document_title?: string }): string {
  const title = source.document_title ?? ''
  if (title.endsWith('.pdf')) return 'PDF'
  if (title.endsWith('.md') || title.endsWith('.txt') || title.endsWith('.doc')) return 'DOC'
  if (title.includes('http://') || title.includes('https://')) return 'URL'
  return 'DB'
}

export function TraceDetails({ trace, onBack }: TraceDetailsProps) {
  const statusInfo = statusBadge[trace.status] || statusBadge.completed

  const sources = trace.response?.sources ?? []
  const toolCalls = trace.response?.tool_calls ?? []
  const parsedOutput = trace.response?.parsed_output ?? null
  const outputParseError = trace.response?.output_parse_error ?? null

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-white truncate">{trace.title}</h3>
          <div className="flex items-center gap-2 mt-1.5">
            <span className={cn('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium', statusInfo.className)}>
              <span className={cn('h-1.5 w-1.5 rounded-full', statusInfo.className.split(' ')[0].replace('bg-', 'bg-'))} />
              {statusInfo.label}
            </span>
            {trace.latency_ms != null && (
              <span className="text-[11px] text-muted font-mono">{formatLatency(trace.latency_ms)}</span>
            )}
          </div>
        </div>
        <button
          onClick={onBack}
          className="shrink-0 rounded-lg p-1 text-muted hover:text-white hover:bg-accent transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Overview Metric Grid */}
      <div>
        <p className="text-[11px] font-medium text-muted uppercase tracking-wider mb-2">Overview</p>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard
            label="Model"
            value={
              <span className="text-xs font-mono">{trace.provider || trace.model ? `${trace.provider || '—'}/${trace.model || '—'}` : '—'}</span>
            }
            icon={<Cpu className="h-3 w-3" />}
          />
          <MetricCard
            label="Latency"
            value={<span className="text-xs font-mono">{formatLatency(trace.latency_ms)}</span>}
            icon={<Clock className="h-3 w-3" />}
          />
          <MetricCard
            label="Prompt Tokens"
            value={<span className="text-xs font-mono">{formatTokens(trace.input_tokens)}</span>}
            icon={<FileText className="h-3 w-3" />}
          />
          <MetricCard
            label="Completion Tokens"
            value={<span className="text-xs font-mono">{formatTokens(trace.output_tokens)}</span>}
            icon={<Brain className="h-3 w-3" />}
          />
          <MetricCard
            label="Total Tokens"
            value={<span className="text-xs font-mono">{formatTokens(trace.total_tokens)}</span>}
            icon={<Hash className="h-3 w-3" />}
          />
        </div>
      </div>

      {/* Trace ID */}
      {trace.trace_id && (
        <div>
          <p className="text-xs font-medium text-muted mb-1">Trace ID</p>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
            <code className="text-xs flex-1 break-all text-white font-mono">{trace.trace_id}</code>
            <CopyButton text={trace.trace_id} />
          </div>
        </div>
      )}

      {/* Parsed Output */}
      {outputParseError ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
          <p className="text-xs font-medium text-red-400 mb-1">Output Parse Error</p>
          <p className="text-xs text-muted break-all">{outputParseError}</p>
        </div>
      ) : parsedOutput ? (
        <JsonCodeBlock
          data={parsedOutput}
          title="Parsed Output"
          maxHeight="max-h-40"
        />
      ) : null}

      {/* Sources */}
      {sources.length > 0 ? (
        <div>
          <p className="text-xs font-medium text-muted mb-1.5">Sources ({sources.length})</p>
          <div className="space-y-1">
            {sources.map((source, idx) => (
              <div key={idx} className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                <span className={cn(
                  'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase',
                  sourceBadge(source) === 'DB' ? 'bg-violet-500/10 text-violet-400' :
                  sourceBadge(source) === 'DOC' ? 'bg-blue-500/10 text-blue-400' :
                  sourceBadge(source) === 'PDF' ? 'bg-orange-500/10 text-orange-400' :
                  'bg-cyan-500/10 text-cyan-400',
                )}>
                  {sourceBadge(source)}
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
        </div>
      ) : null}

      {/* Tool Calls */}
      {toolCalls.length > 0 ? (
        <div>
          <p className="text-xs font-medium text-muted mb-1.5">Tool Calls ({toolCalls.length})</p>
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
                <span className="text-xs text-white flex-1 truncate">{tc.tool_name}</span>
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
        </div>
      ) : null}
    </div>
  )
}
