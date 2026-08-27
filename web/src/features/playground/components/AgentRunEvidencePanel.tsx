import { AlertTriangle, Copy, RefreshCw } from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgentRunDetail } from '@/features/traces/hooks'

function IdRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null
  return (
    <div className="grid grid-cols-[82px_minmax(0,1fr)_22px] items-center gap-2 py-1.5">
      <span className="text-[8px] uppercase tracking-wide text-muted">{label}</span>
      <code className="truncate text-[9px] text-slate-300">{value}</code>
      <button type="button" onClick={() => void navigator.clipboard?.writeText(value)} className="text-muted hover:text-white" title={`Copy ${label}`}><Copy className="h-3 w-3" /></button>
    </div>
  )
}

export function AgentRunEvidencePanel({ runId, traceId }: { runId?: string | null; traceId?: string | null }) {
  const { data, isLoading, isError, refetch } = useAgentRunDetail({
    runId: runId ?? undefined,
    traceId: runId ? undefined : traceId ?? undefined,
  })

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
        <p className="mt-1 text-[9px] text-muted">The Run may still be finalizing. An Observability Trace is not required for this evidence.</p>
        <button type="button" onClick={() => void refetch()} className="mt-3 rounded-lg border border-border px-2.5 py-1.5 text-[9px] text-muted hover:text-white">Retry</button>
      </section>
    )
  }

  const failure = data.failure && typeof data.failure === 'object' ? data.failure : null

  return (
    <div className="space-y-3">
      {data.failure_code || failure ? (
        <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-3">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-red-300">Failure evidence</p>
          <p className="mt-1 text-[10px] text-red-200">{String(failure?.message || data.failure_code || 'Agent Run failed')}</p>
          {data.failure_detail ? <p className="mt-2 whitespace-pre-wrap break-words font-mono text-[9px] leading-4 text-muted">{data.failure_detail}</p> : null}
        </section>
      ) : null}

      <section className="rounded-xl border border-border/75 bg-background/25 p-3">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Technical identifiers</p>
        <div className="mt-1 divide-y divide-border/50">
          <IdRow label="Run" value={data.id} />
          <IdRow label="Trace" value={data.trace_id} />
          <IdRow label="Session" value={data.session_id} />
          <IdRow label="Network" value={data.network_execution_id} />
          <IdRow label="Invocation" value={data.network_invocation_id} />
          <IdRow label="Parent Run" value={data.parent_run_id} />
        </div>
        {data.trace_id ? <p className="mt-2 text-[8px] text-muted">Trace ID is correlation evidence; this panel does not require a persisted Observability Trace.</p> : null}
      </section>

      <section className="rounded-xl border border-border/75 bg-background/25 p-3">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Execution evidence</p>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[9px]">
          <div><span className="text-muted">Status</span><p className="mt-0.5 text-slate-200">{data.status}</p></div>
          <div><span className="text-muted">Origin</span><p className="mt-0.5 text-slate-200">{data.origin}</p></div>
          <div><span className="text-muted">Provider</span><p className="mt-0.5 text-slate-200">{data.provider || '—'}</p></div>
          <div><span className="text-muted">Model</span><p className="mt-0.5 truncate text-slate-200">{data.model || '—'}</p></div>
          <div><span className="text-muted">Tool calls</span><p className="mt-0.5 text-slate-200">{data.tool_calls.length}</p></div>
          <div><span className="text-muted">Sources</span><p className="mt-0.5 text-slate-200">{data.sources.length}</p></div>
        </div>
      </section>

      {data.diagnostics ? (
        <section className="rounded-xl border border-border/75 bg-background/25 p-3">
          <p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Diagnostics</p>
          <JsonCodeBlock value={data.diagnostics} maxHeight={220} />
        </section>
      ) : null}

      {data.llm_calls.length ? (
        <section className="rounded-xl border border-border/75 bg-background/25 p-3">
          <p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Model invocation evidence</p>
          <JsonCodeBlock value={data.llm_calls} maxHeight={260} />
        </section>
      ) : null}

      {data.tool_calls.length ? (
        <section className="rounded-xl border border-border/75 bg-background/25 p-3">
          <p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Tool evidence</p>
          <JsonCodeBlock value={data.tool_calls} maxHeight={240} />
        </section>
      ) : null}

      {data.sources.length ? (
        <section className="rounded-xl border border-border/75 bg-background/25 p-3">
          <p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Source evidence</p>
          <JsonCodeBlock value={data.sources} maxHeight={240} />
        </section>
      ) : null}
    </div>
  )
}
