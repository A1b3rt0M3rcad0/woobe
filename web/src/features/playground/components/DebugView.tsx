import { useState, useRef, useLayoutEffect } from 'react'
import { Bug, CheckCircle, XCircle, AlertTriangle, Copy, ChevronDown, ChevronRight } from 'lucide-react'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatTokens, formatCurrency, formatLatency } from '@/lib/formatters/number'
import type { AskResponse } from '@/features/playground/types'

interface DebugViewProps {
  lastResponse: AskResponse | null
  lastRequestPayload: Record<string, unknown> | null
}

// ── Clamped text (CSS line-clamp + fade gradient) ──

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
        <div className="absolute bottom-0 inset-x-0 h-6 bg-gradient-to-t from-background to-transparent pointer-events-none" />
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

// ── Copyable ID row (aligned grid) ──

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

// ── Collapsible section line ──

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

// ── Collapsible JSON section (for details) ──

function CollapsibleJson({
  title,
  data,
  defaultOpen = false,
  maxHeight = 160,
}: {
  title: string
  data: unknown
  defaultOpen?: boolean
  maxHeight?: number
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
      {open && (
        <div className="px-3 pb-3 pt-1">
          <JsonCodeBlock value={data} maxHeight={maxHeight} />
        </div>
      )}
    </div>
  )
}

// ── Inline usage chips ──

function UsageInline({ usage }: { usage: AskResponse['usage'] }) {
  if (!usage) return null
  const parts: string[] = []
  if (usage.input_tokens != null) parts.push(`Input ${formatTokens(usage.input_tokens)}`)
  if (usage.output_tokens != null) parts.push(`Output ${formatTokens(usage.output_tokens)}`)
  if (usage.total_tokens != null) parts.push(`Total ${formatTokens(usage.total_tokens)}`)
  if (usage.cost_usd != null) parts.push(formatCurrency(usage.cost_usd))
  if (parts.length === 0) return null
  return <p className="text-[11px] text-muted">{parts.join('  ·  ')}</p>
}

// ── Main component ──

export function DebugView({ lastResponse, lastRequestPayload }: DebugViewProps) {
  if (!lastResponse) {
    return (
      <div className="p-4 text-center">
        <Bug className="h-8 w-8 text-muted mx-auto mb-2" />
        <p className="text-sm text-muted">Send a message to inspect debug data.</p>
        <p className="text-xs text-muted mt-1">Debug information will appear here after each request.</p>
      </div>
    )
  }

  const hasDetailSections = !!(
    (lastResponse.sources?.length ?? 0) > 0 ||
    (lastResponse.tool_calls?.length ?? 0) > 0 ||
    lastResponse.parsed_output ||
    lastRequestPayload
  )

  // Parse error blocks the overview (highest priority)
  if (lastResponse.output_parse_error) {
    return (
      <div className="p-4 space-y-2">
        <h3 className="text-sm font-medium text-white">Debug</h3>
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span className="text-xs font-medium text-red-400">Parse Error</span>
          </div>
          <p className="text-xs text-muted break-all">{lastResponse.output_parse_error}</p>
        </div>
        <CollapsibleJson title="Raw" data={lastResponse} />
      </div>
    )
  }

  return (
    <div className="p-4 space-y-1.5">
      <h3 className="text-sm font-medium text-white mb-2">Debug</h3>

      {/* ── Badge row ── */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle className="h-3 w-3" />
          Completed
        </span>
        {lastResponse.latency_ms != null && (
          <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] text-muted font-mono bg-background border border-border">
            {formatLatency(lastResponse.latency_ms)}
          </span>
        )}
        {(lastResponse.provider || lastResponse.model) && (
          <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] text-muted font-mono bg-background border border-border">
            {lastResponse.provider || '—'}/{lastResponse.model || '—'}
          </span>
        )}
        {lastResponse.fallback_used && (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
            <AlertTriangle className="h-3 w-3" />
            Fallback
          </span>
        )}
      </div>

      {/* ── Usage inline ── */}
      <UsageInline usage={lastResponse.usage} />

      {/* ── Answer ── */}
      {lastResponse.answer && (
        <div className="rounded-lg border border-border bg-background p-2.5 mt-2.5">
          <p className="text-[10px] font-medium text-muted uppercase tracking-wider mb-1">Answer</p>
          <ClampedText text={lastResponse.answer} lines={2} />
        </div>
      )}

      {/* ── Detail sections (collapsed by default) ── */}
      {hasDetailSections && (
        <div className="border-t border-border pt-1.5 mt-2.5 space-y-0.5">
          {lastResponse.sources && lastResponse.sources.length > 0 && (
            <CollapsibleSection title="Sources" badge={`${lastResponse.sources.length}`}>
              <JsonCodeBlock value={lastResponse.sources} maxHeight={128} />
            </CollapsibleSection>
          )}
          {lastResponse.tool_calls && lastResponse.tool_calls.length > 0 && (
            <CollapsibleSection title="Tool Calls" badge={`${lastResponse.tool_calls.length}`}>
              <JsonCodeBlock value={lastResponse.tool_calls} maxHeight={128} />
            </CollapsibleSection>
          )}
          {lastResponse.parsed_output && (
            <CollapsibleSection title="Structured Output">
              <JsonCodeBlock value={lastResponse.parsed_output} maxHeight={128} />
            </CollapsibleSection>
          )}
          {lastRequestPayload && (
            <CollapsibleSection title="Request &amp; Context">
              <div className="space-y-1.5">
                <JsonCodeBlock value={lastRequestPayload} maxHeight={128} />
                {!!lastRequestPayload.snapshot_override && (
                  <CollapsibleJson title="Snapshot Override" data={lastRequestPayload.snapshot_override} />
                )}
              </div>
            </CollapsibleSection>
          )}
          <CollapsibleSection title="Raw">
            <JsonCodeBlock value={lastResponse} maxHeight={128} />
          </CollapsibleSection>
        </div>
      )}

      {/* ── IDs list (always at bottom) ── */}
      {!!(
        lastResponse.trace_id ||
        lastResponse.message_id ||
        lastResponse.session_id ||
        lastRequestPayload?.project_id ||
        lastRequestPayload?.agent_id
      ) && (
        <div className="border-t border-border pt-1.5 mt-2.5 space-y-1">
          {lastResponse.trace_id && <CopyableIdRow label="trace" value={lastResponse.trace_id} />}
          {lastResponse.message_id && <CopyableIdRow label="message" value={lastResponse.message_id} />}
          {lastResponse.session_id && <CopyableIdRow label="session" value={lastResponse.session_id} />}
          {!!lastRequestPayload?.project_id && <CopyableIdRow label="project" value={String(lastRequestPayload.project_id)} />}
          {!!lastRequestPayload?.agent_id && <CopyableIdRow label="agent" value={String(lastRequestPayload.agent_id)} />}
        </div>
      )}
    </div>
  )
}
