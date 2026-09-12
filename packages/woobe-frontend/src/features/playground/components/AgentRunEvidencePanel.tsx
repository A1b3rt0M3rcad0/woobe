import { useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Copy,
  Info,
  RefreshCw,
} from 'lucide-react'
import { EmptyStatePanel, SectionBlock } from '@woobe/ui'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { operationCountsLabel } from '@/features/skills/operations'
import { useAgentRunDetail, useOptionalTraceDetail } from '@/features/traces/hooks'
import { ToolCallsCollapsible } from './ToolCallsCollapsible'

function CollapsibleSection({ title, badge, children }: { title: string; badge?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="border-t border-border/60 first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-[34px] w-full items-center gap-2 px-2.5 py-2 text-left font-mono text-[8px] text-muted-foreground transition-colors hover:bg-control/25 hover:text-slate-50"
        aria-expanded={open}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="font-semibold">{title}</span>
        {badge ? <span className="ml-auto rounded-technical border border-border bg-control/30 px-1.5 py-0.5 text-[8px] text-muted-foreground">{badge}</span> : null}
      </button>
      {open ? <div className="px-2.5 pb-2.5">{children}</div> : null}
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
    <div className="grid grid-cols-[76px_minmax(0,1fr)_24px] items-center gap-2 py-1.5">
      <span className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{label}</span>
      <code className="truncate font-mono text-[8px] text-slate-300">{value}</code>
      <button type="button" onClick={copy} className="flex h-6 w-6 items-center justify-center rounded-technical border border-transparent text-muted-foreground hover:border-border hover:bg-control hover:text-slate-50" title={copied ? 'Copied' : `Copy ${label}`} aria-label={`Copy ${label}`}><Copy className="h-3 w-3" /></button>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l border-border/60 pl-2 first:border-l-0 first:pl-0">
      <p className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
      <p className="mt-0.5 truncate font-mono text-[9px] text-slate-200">{value}</p>
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
    return <EmptyStatePanel compact icon={<RefreshCw className="h-4 w-4 animate-spin" />} title="Loading Run evidence" />
  }

  if (isError || !data) {
    return <EmptyStatePanel compact icon={<AlertTriangle className="h-4 w-4 text-amber-300" />} title="Run evidence unavailable" description="The Run may still be finalizing. Durable Run evidence does not require a separate Observability Trace." action={<button type="button" onClick={() => void refetch()} className="h-[27px] rounded-control border border-border bg-control/35 px-2.5 font-mono text-[8px] text-slate-200 hover:bg-control">Retry</button>} />
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
    <div className="space-y-3">
      <SectionBlock
        density="compact"
        eyebrow="Evidence"
        title="Durable execution evidence"
        description="Technical and causal evidence stays separate from the operational Run view until it is needed."
        actions={<Info className="h-3.5 w-3.5 text-muted-foreground" aria-label="Durable Agent Run and observability evidence" />}
      >
        <div className="grid grid-cols-3 gap-2 border-t border-border/60 pt-2.5 sm:grid-cols-6">
          <MetaItem label="Status" value={data.status} />
          <MetaItem label="Origin" value={data.origin} />
          <MetaItem label="Provider" value={data.provider || '—'} />
          <MetaItem label="Model" value={data.model || '—'} />
          <MetaItem label="Operations" value={operationCountsLabel(data.tool_calls)} />
          <MetaItem label="Sources" value={String(data.sources.length)} />
        </div>
      </SectionBlock>

      {data.failure_code || failure ? (
        <div className="rounded-container border border-red-500/20 bg-background/30 px-3 py-2.5">
          <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.08em] text-red-300">Failure evidence</p>
          <p className="mt-1 font-sans text-[9px] leading-4 text-red-100">{String(failure?.message || data.failure_code || 'Agent Run failed')}</p>
          {data.failure_detail ? <p className="mt-2 whitespace-pre-wrap break-words font-mono text-[8px] leading-4 text-muted-foreground">{data.failure_detail}</p> : null}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-container border border-border/75 bg-background/20">
        <CollapsibleSection title="Diagnostics" badge={data.diagnostics ? 'available' : 'none'}>
          {data.diagnostics ? <JsonCodeBlock value={data.diagnostics} maxHeight={220} /> : <p className="font-sans text-[9px] text-muted-foreground">No diagnostics payload persisted.</p>}
        </CollapsibleSection>

        {data.llm_calls.length ? <CollapsibleSection title="Model invocations" badge={String(data.llm_calls.length)}><JsonCodeBlock value={data.llm_calls} maxHeight={280} /></CollapsibleSection> : null}
        {data.tool_calls.length ? <CollapsibleSection title="Tool / Skill evidence" badge={String(data.tool_calls.length)}><ToolCallsCollapsible toolCalls={data.tool_calls} /></CollapsibleSection> : null}
        {data.sources.length ? <CollapsibleSection title="Context / Source evidence" badge={String(data.sources.length)}><JsonCodeBlock value={data.sources} maxHeight={260} /></CollapsibleSection> : null}

        <CollapsibleSection title="Observability events" badge={optionalTrace.isLoading ? 'loading' : String(events.length)}>
          {events.length ? <JsonCodeBlock value={events} maxHeight={300} /> : optionalTrace.isLoading ? <div className="flex items-center gap-2 font-sans text-[9px] text-muted-foreground"><RefreshCw className="h-3 w-3 animate-spin" />Loading Trace events…</div> : <p className="font-sans text-[9px] leading-4 text-muted-foreground">No separate Observability Trace events were materialized. Durable Agent Run evidence remains authoritative.</p>}
        </CollapsibleSection>

        <CollapsibleSection title="Technical identifiers" badge={String(identifierCount)}>
          <div className="divide-y divide-border/50">{identifiers.map(([label, value]) => <IdRow key={label} label={label} value={value} />)}</div>
        </CollapsibleSection>

        <CollapsibleSection title="Raw payload">
          <JsonCodeBlock value={{ diagnostics: data.diagnostics ?? null, model_invocations: data.llm_calls, tool_calls: data.tool_calls, sources: data.sources, observability_events: events }} maxHeight={320} />
        </CollapsibleSection>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 font-mono text-[8px] text-muted-foreground">
        <span>{data.llm_calls.length} model invocation{data.llm_calls.length === 1 ? '' : 's'}</span>
        <span>{data.tool_calls.length} tool/skill operation{data.tool_calls.length === 1 ? '' : 's'}</span>
        <span>{data.sources.length} source{data.sources.length === 1 ? '' : 's'}</span>
        <span>{events.length} event{events.length === 1 ? '' : 's'}</span>
      </div>
    </div>
  )
}
