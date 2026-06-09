import { useState } from 'react'
import { ChevronDown, ChevronRight, Bug } from 'lucide-react'
import { MetricCard } from './MetricCard'
import { JsonCodeBlock } from './JsonCodeBlock'
import { CopyButton } from '@/components/common/CopyButton'
import { Separator } from '@/components/ui/Separator'
import { formatNumber } from '@/lib/formatters/number'
import type { AskResponse } from '@/features/playground/types'

interface DebugViewProps {
  lastResponse: AskResponse | null
}

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs font-medium text-muted hover:text-white hover:bg-accent transition-colors"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {title}
      </button>
      {open && <div className="px-3 pb-3 pt-1">{children}</div>}
    </div>
  )
}

export function DebugView({ lastResponse }: DebugViewProps) {
  const [activeSection, setActiveSection] = useState<string | null>(null)

  if (!lastResponse) {
    return (
      <div className="p-4 text-center">
        <Bug className="h-8 w-8 text-muted mx-auto mb-2" />
        <p className="text-sm text-muted">Send a message to inspect debug data.</p>
        <p className="text-xs text-muted mt-1">Debug information will appear here after each request.</p>
      </div>
    )
  }

  const normalizedEnvelope = { success: true, data: lastResponse }

  return (
    <div className="p-4 space-y-2">
      <h3 className="text-sm font-medium text-white mb-2">Debug</h3>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2">
        {lastResponse.latency_ms != null && (
          <MetricCard label="Latency" value={`${Math.round(lastResponse.latency_ms)}ms`} />
        )}
        {lastResponse.model && (
          <MetricCard
            label="Model / Provider"
            value={<span className="text-xs">{lastResponse.provider || '—'} / {lastResponse.model}</span>}
          />
        )}
        {lastResponse.usage?.input_tokens != null && (
          <MetricCard label="Input Tokens" value={formatNumber(lastResponse.usage.input_tokens, 0)} />
        )}
        {lastResponse.usage?.output_tokens != null && (
          <MetricCard label="Output Tokens" value={formatNumber(lastResponse.usage.output_tokens, 0)} />
        )}
        {lastResponse.usage?.total_tokens != null && (
          <MetricCard label="Total Tokens" value={formatNumber(lastResponse.usage.total_tokens, 0)} />
        )}

      </div>

      {lastResponse.trace_id && (
        <div className="rounded-lg border border-border bg-background p-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-muted">Trace ID</p>
            <CopyButton text={lastResponse.trace_id} />
          </div>
          <p className="text-xs text-white font-mono mt-1 break-all">{lastResponse.trace_id}</p>
        </div>
      )}

      {lastResponse.fallback_used && (
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3">
          <p className="text-xs font-medium text-yellow-400">Fallback Used</p>
          <p className="text-xs text-muted mt-1">Primary model failed; fallback was used for this request.</p>
        </div>
      )}

      <Separator />

      {/* Collapsible Debug Sections */}
      <div className="space-y-1.5">
        <CollapsibleSection title="Normalized Response" defaultOpen>
          <JsonCodeBlock data={normalizedEnvelope} maxHeight="max-h-40" />
        </CollapsibleSection>

        <CollapsibleSection title="Request">
          <p className="text-xs text-muted mb-1">Payload sent to /runtime/ask</p>
          <JsonCodeBlock
            data={{ agent_id: '...', message: '...' }}
            maxHeight="max-h-32"
          />
        </CollapsibleSection>

        <CollapsibleSection title="Raw Response">
          <p className="text-xs text-muted mb-1">Raw HTTP response data</p>
          <JsonCodeBlock data={lastResponse} maxHeight="max-h-40" />
        </CollapsibleSection>

        {lastResponse.sources && lastResponse.sources.length > 0 && (
          <CollapsibleSection title={`Sources (${lastResponse.sources.length})`}>
            <JsonCodeBlock data={lastResponse.sources} maxHeight="max-h-32" />
          </CollapsibleSection>
        )}

        {lastResponse.tool_calls && lastResponse.tool_calls.length > 0 && (
          <CollapsibleSection title={`Tool Calls (${lastResponse.tool_calls.length})`}>
            <JsonCodeBlock data={lastResponse.tool_calls} maxHeight="max-h-32" />
          </CollapsibleSection>
        )}

        {lastResponse.parsed_output && (
          <CollapsibleSection title="Structured Output" defaultOpen>
            <JsonCodeBlock data={lastResponse.parsed_output} maxHeight="max-h-32" />
          </CollapsibleSection>
        )}

        {lastResponse.output_parse_error && (
          <CollapsibleSection title="Parse Error" defaultOpen>
            <div className="rounded bg-red-500/10 border border-red-500/30 p-2">
              <p className="text-xs text-red-400">The model did not return valid JSON.</p>
              <p className="text-xs text-muted mt-1 break-all">{lastResponse.output_parse_error}</p>
            </div>
          </CollapsibleSection>
        )}
      </div>
    </div>
  )
}
