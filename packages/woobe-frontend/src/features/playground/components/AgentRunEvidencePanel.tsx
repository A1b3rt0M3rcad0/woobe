import { useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Copy,
  Info,
  RefreshCw,
} from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { operationCountsLabel } from '@/features/skills/operations'
import { useAgentRunDetail, useOptionalTraceDetail } from '@/features/traces/hooks'
import { ToolCallsCollapsible } from './ToolCallsCollapsible'

function CollapsibleSection({ title, badge, children }: { title: string; badge?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)

  return (
    <section className="border-t border-border/70 first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 py-2.5 text-left text-[10px] font-medium text-muted transition-colors hover:text-white"
        aria-expanded={open}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span>{title}</span>
        {badge ? <span className="ml-auto text-[9px] font-normal text-muted">{badge}</span> : null}
      </button>
      {open ? <div className="pb-3">{children}</div> : null}
    </section>
  )
}

function IdRow({ label, value }: { label: string; value?: string | null }) {
  const [copied, setCopied] = useState(false)
  if (!value) return null

  const copy = () => {
    void navigator.clipboard?.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  return (
    <div className="grid grid-cols-[86px_minmax(0,1fr)_24px] items-center gap-2 py-1.5">
      <span className="text-[8px] uppercase tracking-wide text-muted">{label}</span>
      <code className="truncate text-[9px] text-slate-300">{value}</code>
      <button type="button" onClick={copy} className="text-muted hover:text-white" title={copied ? 'Copied' : `Copy ${label}`} aria-label={`Copy ${label}`}>
        <Copy className="h-3 w-3" />
      </button>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[8px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 truncate text-[10px] font-medium text-slate-200">{value}</p>
    </div>
  )
}

export function AgentRunEvidencePanel({ runId, traceId }: { runId?: string | null; traceId?: string | null }) {
  const { data, isLoading, isError, refetch } = useAgentRunDetail({
    runId: runId ?? undefined,
    traceId: runId ? undefined : traceId ?? undefined,
  })
  const optionalTrace = useOptionalTraceDetail(traceId ?? data?.trace_id ?? undefined)

  if (isLoading) {
    return (
      <section className="rounded-xl border border-border/75 bg-background/20 px-4 py-8 text-center">
        <RefreshCw className="mx-auto h-4 w-4 animate-spin text-muted" />
        <p className="mt-2 text-[10px] text-muted">Loading Agent Run evidence...</p>
      </section>
    )
  }

  if (isError || !data) {
    return (
      <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-5 text-center">
        <AlertTriangle className="mx-auto h-4 w-4 text-amber-300" />
        <p className="mt-2 text-[10px] font-medium text-amber-200">Agent Run evidence is unavailable.</p>
        <p className="mt-1 text-[9px] text-muted">The Run may still be finalizing. An Observability Trace is not required for durable Run evidence.</p>
        <button type="button" onClick={() => void refetch()} className="mt-3 rounded-lg border border-border px-2.5 py-1.5 text-[9px] text-muted hover:text-white">Retry</button>
      </section>
    )
  }

  const failure = data.failure && typeof data.failure === 'object' ? data.failure : null
  const events = optionalTrace.data?.events ?? []
  const identifiers = [
    ['Run', data.id],
    ['Trace', data.trace_id],
    ['Session', data.session_id],
    ['Network', data.network_execution_id],
    ['Invocation', data.network_invocation_id],
    ['Parent Run', data.parent_run_id],
  ] as const
  const identifierCount = identifiers.filter(([, value]) => Boolean(value)).length

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Evidence</p>
          <Info className="h-3 w-3 text-muted" aria-label="Durable Agent Run and observability evidence" />
        </div>
        <p className="mt-1 text-[9px] leading-4 text-muted">Technical and causal evidence is preserved here and stays out of the operational Run view until needed.</p>
      </div>

      {data.failure_code || failure ? (
        <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-3">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-red-300">Failure evidence</p>
          <p className="mt-1 text-[10px] text-red-200">{String(failure?.message || data.failure_code || 'Agent Run failed')}</p>
          {data.failure_detail ? <p className="mt-2 whitespace-pre-wrap break-words font-mono text-[9px] leading-4 text-muted">{data.failure_detail}</p> : null}
        </section>
      ) : null}

      <div className="rounded-xl border border-border/75 bg-background/20 px-3">
        <CollapsibleSection title="Execution evidence" badge={data.status}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg bg-background/35 p-2.5">
            <MetaItem label="Status" value={data.status} />
            <MetaItem label="Origin" value={data.origin} />
            <MetaItem label="Provider" value={data.provider || '—'} />
            <MetaItem label="Model" value={data.model || '—'} />
            <MetaItem label="Operations" value={operationCountsLabel(data.tool_calls)} />
            <MetaItem label="Sources" value={String(data.sources.length)} />
          </div>
          {data.diagnostics ? (
            <details className="group mt-2 border-t border-border/70 pt-2">
              <summary className="flex cursor-pointer list-none items-center gap-1 text-[9px] text-muted hover:text-white">
                <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />
                Diagnostics payload
              </summary>
              <JsonCodeBlock value={data.diagnostics} maxHeight={220} className="mt-2" />
            </details>
          ) : null}
        </CollapsibleSection>

        {data.llm_calls.length ? (
          <CollapsibleSection title="Model invocations" badge={String(data.llm_calls.length)}>
            <JsonCodeBlock value={data.llm_calls} maxHeight={280} />
          </CollapsibleSection>
        ) : null}

        {data.tool_calls.length ? (
          <CollapsibleSection title="Tool/Skill evidence" badge={String(data.tool_calls.length)}>
            <ToolCallsCollapsible toolCalls={data.tool_calls} />
          </CollapsibleSection>
        ) : null}

        {data.sources.length ? (
          <CollapsibleSection title="Context / Source evidence" badge={String(data.sources.length)}>
            <JsonCodeBlock value={data.sources} maxHeight={260} />
          </CollapsibleSection>
        ) : null}

        <CollapsibleSection title="Events" badge={optionalTrace.isLoading ? 'loading' : String(events.length)}>
          {events.length ? (
            <JsonCodeBlock value={events} maxHeight={300} />
          ) : optionalTrace.isLoading ? (
            <div className="flex items-center gap-2 text-[9px] text-muted"><RefreshCw className="h-3 w-3 animate-spin" />Loading Observability Trace events...</div>
          ) : (
            <p className="text-[9px] leading-4 text-muted">No separate Observability Trace events were materialized. Durable Agent Run evidence remains authoritative.</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="Raw">
          <JsonCodeBlock
            value={{
              diagnostics: data.diagnostics ?? null,
              model_invocations: data.llm_calls,
              tool_calls: data.tool_calls,
              sources: data.sources,
              observability_events: events,
            }}
            maxHeight={320}
          />
        </CollapsibleSection>

        <CollapsibleSection title="Technical identifiers" badge={String(identifierCount)}>
          <div className="divide-y divide-border/50">
            {identifiers.map(([label, value]) => <IdRow key={label} label={label} value={value} />)}
          </div>
          {data.trace_id ? <p className="mt-2 text-[8px] leading-3.5 text-muted">Trace ID is correlation evidence; this panel does not require a persisted Observability Trace.</p> : null}
        </CollapsibleSection>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 text-[8px] text-muted">
        <span>{data.llm_calls.length} Model Invocation{data.llm_calls.length === 1 ? '' : 's'}</span>
        <span>{data.tool_calls.length} Tool/Skill operation{data.tool_calls.length === 1 ? '' : 's'}</span>
        <span>{data.sources.length} source{data.sources.length === 1 ? '' : 's'}</span>
        <span>{events.length} event{events.length === 1 ? '' : 's'}</span>
      </div>
    </div>
  )
}
