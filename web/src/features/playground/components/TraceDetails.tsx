import { MetricCard } from './MetricCard'
import { JsonCodeBlock } from './JsonCodeBlock'
import { CopyButton } from '@/components/common/CopyButton'
import { Clock, Cpu, FileText, DollarSign, Hash, Brain, Wrench, Globe } from 'lucide-react'
import { formatNumber, formatCurrency } from '@/lib/formatters/number'
import type { TraceItem } from '@/features/playground/types'

interface TraceDetailsProps {
  trace: TraceItem
  onBack: () => void
}

export function TraceDetails({ trace, onBack }: TraceDetailsProps) {
  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={onBack} className="text-xs text-primary hover:underline">&larr; Back</button>
        <h3 className="text-sm font-medium text-white truncate">{trace.title}</h3>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <MetricCard
          label="Model"
          value={
            <span className="text-xs">{trace.provider || '—'} / {trace.model || '—'}</span>
          }
          icon={<Cpu className="h-3 w-3" />}
        />
        <MetricCard
          label="Latency"
          value={trace.latency_ms != null ? `${Math.round(trace.latency_ms)}ms` : '—'}
          icon={<Clock className="h-3 w-3" />}
        />
        <MetricCard
          label="Prompt Tokens"
          value={formatNumber(trace.input_tokens, 0)}
          icon={<FileText className="h-3 w-3" />}
        />
        <MetricCard
          label="Completion Tokens"
          value={formatNumber(trace.output_tokens, 0)}
          icon={<Brain className="h-3 w-3" />}
        />
        <MetricCard
          label="Total Tokens"
          value={formatNumber(trace.total_tokens, 0)}
          icon={<Hash className="h-3 w-3" />}
        />
        <MetricCard
          label="Cost"
          value={formatCurrency(trace.cost_usd, 6)}
          icon={<DollarSign className="h-3 w-3" />}
        />
      </div>

      {trace.trace_id && (
        <div>
          <p className="text-xs font-medium text-muted mb-1">Trace ID</p>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
            <code className="text-xs flex-1 break-all">{trace.trace_id}</code>
            <CopyButton text={trace.trace_id} />
          </div>
        </div>
      )}

      {trace.response?.parsed_output && (
        <JsonCodeBlock
          data={trace.response.parsed_output}
          title="Parsed Output"
          maxHeight="max-h-32"
        />
      )}

      {trace.response?.sources && trace.response.sources.length > 0 && (
        <JsonCodeBlock
          data={trace.response.sources}
          title={`Sources (${trace.response.sources.length})`}
          maxHeight="max-h-32"
          copyText={JSON.stringify(trace.response.sources, null, 2)}
        />
      )}

      {trace.response?.tool_calls && trace.response.tool_calls.length > 0 && (
        <JsonCodeBlock
          data={trace.response.tool_calls}
          title={`Tool Calls (${trace.response.tool_calls.length})`}
          maxHeight="max-h-32"
          copyText={JSON.stringify(trace.response.tool_calls, null, 2)}
        />
      )}
    </div>
  )
}
