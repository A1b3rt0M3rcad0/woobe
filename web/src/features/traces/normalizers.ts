import type {
  Trace,
  TraceDetail,
  TraceDetailNormalized,
  TraceEvent,
  TraceSource,
  TraceStatus,
  TraceSummary,
  TraceToolCall,
  TraceUsage,
} from './types'

function inferTitle(trace: Trace): string {
  if (trace.data?.title && typeof trace.data.title === 'string') {
    return trace.data.title
  }
  const eventPayload = trace.data as Record<string, unknown> | undefined
  const message = eventPayload?.message as string | undefined
  if (message && typeof message === 'string') {
    return message.slice(0, 80).replace(/\n/g, ' ') + (message.length > 80 ? '...' : '')
  }
  if (trace.status === 'failed') {
    const err = trace.error
    return err ? `Failed: ${err.slice(0, 60)}` : 'Failed execution'
  }
  if (trace.model) {
    return `Agent execution (${trace.model})`
  }
  return 'Agent execution'
}

function normalizeStatus(raw: string): TraceStatus {
  const lower = raw.toLowerCase()
  if (lower === 'success' || lower === 'completed') return 'completed'
  if (lower === 'error' || lower === 'failed') return 'failed'
  if (lower === 'running' || lower === 'processing') return 'running'
  if (lower === 'pending' || lower === 'queued') return 'pending'
  if (lower === 'cancelled' || lower === 'canceled') return 'cancelled'
  return 'completed'
}

function safeNumber(val: unknown): number | null {
  if (typeof val === 'number' && !Number.isNaN(val)) return val
  return null
}

export function normalizeTraceSummary(raw: Trace): TraceSummary {
  const data = (raw.data ?? {}) as Record<string, unknown>
  return {
    id: raw.id,
    projectId: raw.project_id,
    agentId: raw.agent_id ?? null,
    sessionId: raw.session_id ?? null,
    title: inferTitle(raw),
    status: normalizeStatus(raw.status),
    model: raw.model ?? null,
    provider: raw.provider ?? null,
    latencyMs: safeNumber(raw.total_latency_ms),
    inputTokens: safeNumber(data.input_tokens),
    outputTokens: safeNumber(data.output_tokens),
    totalTokens: safeNumber(data.total_tokens),
    costUsd: safeNumber(data.cost_usd ?? raw.total_cost_usd),
    createdAt: raw.created_at ?? null,
  }
}

function normalizeSources(raw: unknown): TraceSource[] {
  if (!Array.isArray(raw)) return []
  return raw.map((s: Record<string, unknown>) => ({
    document_id: (s.document_id as string) ?? null,
    document_title: (s.document_title as string) ?? null,
    chunk_id: (s.chunk_id as string) ?? null,
    page_number: safeNumber(s.page_number),
    score: safeNumber(s.score),
    content_preview: (s.content_preview as string) ?? null,
  }))
}

function normalizeToolCalls(raw: unknown): TraceToolCall[] {
  if (!Array.isArray(raw)) return []
  return raw.map((t: Record<string, unknown>) => ({
    tool_name: (t.tool_name as string) ?? 'unknown',
    input: t.input ?? null,
    output: t.output ?? null,
    duration_ms: safeNumber(t.duration_ms),
    status: (t.status as string) ?? null,
    latency_ms: safeNumber(t.latency_ms),
    error: (t.error as string) ?? null,
  }))
}

function normalizeEvents(raw: unknown): TraceEvent[] {
  if (!Array.isArray(raw)) return []
  return raw.map((e: Record<string, unknown>) => ({
    id: (e.id as string) ?? '',
    trace_id: (e.trace_id as string) ?? '',
    event_type: (e.event_type as string) ?? 'info',
    latency_ms: safeNumber(e.latency_ms),
    cost_usd: safeNumber(e.cost_usd),
    payload: (e.payload as Record<string, unknown>) ?? null,
    payload_ref: (e.payload_ref as string) ?? null,
    created_at: (e.created_at as string) ?? null,
  }))
}

export function normalizeTraceDetail(raw: TraceDetail): TraceDetailNormalized {
  const summary = normalizeTraceSummary(raw.trace)
  const data = (raw.trace.data ?? {}) as Record<string, unknown>

  const usage: TraceUsage = {
    inputTokens: safeNumber(data.input_tokens),
    outputTokens: safeNumber(data.output_tokens),
    totalTokens: safeNumber(data.total_tokens),
    costUsd: safeNumber(data.cost_usd ?? raw.trace.total_cost_usd),
  }

  return {
    ...summary,
    usage,
    parsedOutput: data.parsed_output ?? null,
    outputParseError: (data.output_parse_error as string) ?? null,
    sources: normalizeSources(data.sources),
    toolCalls: normalizeToolCalls(data.tool_calls),
    events: normalizeEvents(raw.events),
  }
}
