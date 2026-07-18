import { useState, type ReactNode } from 'react'
import { Activity, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Copy, XCircle } from 'lucide-react'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatTokens, formatCurrency, formatLatency } from '@/lib/formatters/number'
import type { AskResponse, RawStreamEvent } from '@/features/playground/types'

interface DebugViewProps {
  lastResponse: AskResponse | null
  lastRequestPayload: Record<string, unknown> | null
  rawEvents?: RawStreamEvent[]
}

function CollapsibleSection({ title, badge, children, defaultOpen = false }: { title: string; badge?: string; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="border-t border-border/70 first:border-t-0">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-1.5 py-2 text-xs font-medium text-muted transition-colors hover:text-white" aria-expanded={open}>
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span>{title}</span>{badge && <span className="ml-auto text-[10px] text-muted">{badge}</span>}
      </button>
      {open && <div className="pb-3">{children}</div>}
    </section>
  )
}

function CopyableIdRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(value)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }
  return (
    <div className="grid grid-cols-[72px_minmax(0,1fr)_22px] items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5">
      <span className="text-[10px] uppercase text-muted">{label}</span>
      <code className="truncate text-[11px] text-white">{value}</code>
      <button type="button" onClick={copy} className="text-muted hover:text-white" title={copied ? 'Copied' : 'Copy'}><Copy className="h-3 w-3" /></button>
    </div>
  )
}

function UsageSummary({ usage }: { usage: AskResponse['usage'] }) {
  if (!usage) return <p className="text-xs text-muted">Usage was not consolidated for this Run.</p>
  const items = [
    ['Input', usage.input_tokens == null ? '—' : formatTokens(usage.input_tokens)],
    ['Output', usage.output_tokens == null ? '—' : formatTokens(usage.output_tokens)],
    ['Total', usage.total_tokens == null ? '—' : formatTokens(usage.total_tokens)],
    ['Cost', usage.cost_usd == null ? 'Unknown' : formatCurrency(usage.cost_usd)],
  ]
  return <div className="grid grid-cols-2 gap-2">{items.map(([label, value]) => <div key={label} className="rounded-lg border border-border bg-background/55 p-2"><p className="text-[10px] uppercase text-muted">{label}</p><p className="mt-1 text-xs font-medium text-white">{value}</p></div>)}</div>
}

function EventTimeline({ events }: { events: RawStreamEvent[] }) {
  return (
    <div className="space-y-1.5">
      {events.map((event, index) => (
        <div key={`${event.type}-${event.timestamp}-${index}`} className="rounded-lg border border-border bg-background px-3 py-2">
          <div className="flex items-center justify-between gap-2"><code className="truncate text-[11px] text-white">{event.type}</code><span className="shrink-0 text-[10px] text-muted">{new Date(event.timestamp).toLocaleTimeString()}</span></div>
          <JsonCodeBlock value={event.payload} maxHeight={88} className="mt-1" />
        </div>
      ))}
    </div>
  )
}

export function DebugView({ lastResponse, lastRequestPayload, rawEvents = [] }: DebugViewProps) {
  if (!lastResponse) {
    return (
      <div className="p-4 text-center">
        <Activity className="mx-auto h-8 w-8 text-muted/50" />
        <p className="mt-2 text-sm font-medium text-white">No current Agent Run</p>
        <p className="mt-1 text-xs leading-5 text-muted">Send a message to create an Agent Run. Its result, activity, cost, and diagnostic evidence will appear here.</p>
      </div>
    )
  }

  const failed = Boolean(lastResponse.output_parse_error)
  const StatusIcon = failed ? XCircle : CheckCircle
  const toolCount = lastResponse.tool_calls?.length ?? 0
  const sourceCount = lastResponse.sources?.length ?? 0

  return (
    <div className="space-y-4 p-4">
      <header>
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-primary-light">Current Agent Run</p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${failed ? 'border-red-500/25 bg-red-500/10 text-red-300' : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'}`}><StatusIcon className="h-3 w-3" />{failed ? 'Failed' : 'Completed'}</span>
          {lastResponse.latency_ms != null && <span className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-[11px] text-muted">{formatLatency(lastResponse.latency_ms)}</span>}
          {(lastResponse.provider || lastResponse.model) && <span className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-[11px] text-muted">{lastResponse.provider || '—'}/{lastResponse.model || '—'}</span>}
          {lastResponse.fallback_used && <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300"><AlertTriangle className="h-3 w-3" />Fallback</span>}
        </div>
      </header>

      {failed && <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-3"><p className="text-xs font-medium text-red-300">Run output validation failed</p><p className="mt-1 break-words text-xs text-muted">{lastResponse.output_parse_error}</p></section>}

      <section className="rounded-xl border border-border/80 bg-background/35 p-3">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Result</p>
        <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-white">{lastResponse.answer || 'The Agent Run produced no final response.'}</p>
      </section>

      <section>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted">Usage</p>
        <UsageSummary usage={lastResponse.usage} />
      </section>

      <section className="rounded-xl border border-border/80 bg-background/30 p-3">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Activity</p>
        <div className="mt-2 grid grid-cols-3 gap-2 text-center"><div><p className="text-lg font-semibold text-white">{toolCount}</p><p className="text-[10px] text-muted">Tool Calls</p></div><div><p className="text-lg font-semibold text-white">{sourceCount}</p><p className="text-[10px] text-muted">Sources</p></div><div><p className="text-lg font-semibold text-white">{rawEvents.length}</p><p className="text-[10px] text-muted">Events</p></div></div>
      </section>

      <div className="rounded-xl border border-border/80 bg-background/20 px-3">
        {lastResponse.tool_calls?.length ? <CollapsibleSection title="Tool Calls" badge={String(toolCount)}><JsonCodeBlock value={lastResponse.tool_calls} maxHeight={180} /></CollapsibleSection> : null}
        {lastResponse.sources?.length ? <CollapsibleSection title="Sources" badge={String(sourceCount)}><JsonCodeBlock value={lastResponse.sources} maxHeight={180} /></CollapsibleSection> : null}
        {lastResponse.parsed_output ? <CollapsibleSection title="Structured Output"><JsonCodeBlock value={lastResponse.parsed_output} maxHeight={180} /></CollapsibleSection> : null}
        {lastRequestPayload ? <CollapsibleSection title="Request & Context"><JsonCodeBlock value={lastRequestPayload} maxHeight={180} /></CollapsibleSection> : null}
        {rawEvents.length ? <CollapsibleSection title="Run Activity Timeline" badge={String(rawEvents.length)}><EventTimeline events={rawEvents} /></CollapsibleSection> : null}
        <CollapsibleSection title="Diagnostics"><JsonCodeBlock value={{ response: lastResponse, events: rawEvents }} maxHeight={240} /></CollapsibleSection>
      </div>

      {(lastResponse.trace_id || lastResponse.session_id || lastResponse.message_id) && (
        <section className="space-y-1.5 border-t border-border pt-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Technical identifiers</p>
          {lastResponse.trace_id && <CopyableIdRow label="Trace" value={lastResponse.trace_id} />}
          {lastResponse.session_id && <CopyableIdRow label="Session" value={lastResponse.session_id} />}
          {lastResponse.message_id && <CopyableIdRow label="Message" value={lastResponse.message_id} />}
        </section>
      )}
    </div>
  )
}
