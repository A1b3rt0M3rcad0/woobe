import type {
  FallbackInfo,
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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function inferTitle(trace: Trace): string {
  const data = asRecord(trace.data)
  const message = data.message_preview ?? data.message
  if (typeof data.title === 'string' && data.title) return data.title
  if (typeof message === 'string' && message) {
    return message.slice(0, 80).replace(/\n/g, ' ') + (message.length > 80 ? '...' : '')
  }
  if (trace.status === 'failed') {
    return trace.error ? `Failed: ${trace.error.slice(0, 60)}` : 'Failed execution'
  }
  if (trace.model) return `Agent execution (${trace.model})`
  return 'Agent execution'
}

function normalizeStatus(raw: string): TraceStatus {
  const lower = raw.toLowerCase()
  if (lower === 'success' || lower === 'completed') return 'completed'
  if (lower === 'error' || lower === 'failed') return 'failed'
  if (lower === 'running' || lower === 'processing') return 'running'
  if (lower === 'pending' || lower === 'queued') return 'pending'
  if (lower === 'cancelled' || lower === 'canceled') return 'cancelled'
  return 'pending'
}

function safeNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function normalizeFallbackInfo(raw: unknown): FallbackInfo | null {
  const fallback = asRecord(raw)
  if (Object.keys(fallback).length === 0) return null
  return {
    primary_model: typeof fallback.primary_model === 'string' ? fallback.primary_model : null,
    primary_provider: typeof fallback.primary_provider === 'string' ? fallback.primary_provider : null,
    primary_error: typeof fallback.primary_error === 'string' ? fallback.primary_error : '',
    fallback_model: typeof fallback.fallback_model === 'string' ? fallback.fallback_model : null,
    fallback_provider: typeof fallback.fallback_provider === 'string' ? fallback.fallback_provider : null,
    fallback_credential_id:
      typeof fallback.fallback_credential_id === 'string' ? fallback.fallback_credential_id : null,
  }
}

export function normalizeTraceSummary(raw: Trace): TraceSummary {
  const data = asRecord(raw.data)
  return {
    id: raw.id,
    projectId: raw.project_id,
    agentId: raw.agent_id ?? null,
    sessionId: raw.session_id ?? null,
    messageId: typeof data.message_id === 'string' ? data.message_id : null,
    title: inferTitle(raw),
    status: normalizeStatus(raw.status),
    model: raw.model ?? (typeof data.model === 'string' ? data.model : null),
    provider: raw.provider ?? (typeof data.provider === 'string' ? data.provider : null),
    latencyMs: safeNumber(raw.total_latency_ms ?? data.latency_ms),
    inputTokens: safeNumber(data.input_tokens),
    outputTokens: safeNumber(data.output_tokens),
    totalTokens: safeNumber(data.total_tokens),
    costUsd: safeNumber(data.cost_usd ?? raw.total_cost_usd),
    createdAt: raw.created_at ?? null,
    fallbackUsed: Boolean(raw.fallback_used ?? data.fallback_used),
    fallbackInfo: normalizeFallbackInfo(data.fallback_info),
  }
}

function normalizeSources(raw: unknown): TraceSource[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    const source = asRecord(item)
    return {
      document_id: typeof source.document_id === 'string' ? source.document_id : null,
      document_title: typeof source.document_title === 'string' ? source.document_title : null,
      chunk_id: typeof source.chunk_id === 'string' ? source.chunk_id : null,
      page_number: safeNumber(source.page_number),
      score: safeNumber(source.score),
      content_preview: typeof source.content_preview === 'string' ? source.content_preview : null,
    }
  })
}

function normalizeToolCalls(raw: unknown): TraceToolCall[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    const call = asRecord(item)
    const success = typeof call.success === 'boolean' ? call.success : null
    const explicitStatus = typeof call.status === 'string' ? call.status : null
    return {
      tool_name: typeof call.tool_name === 'string' ? call.tool_name : 'unknown',
      input: call.input ?? null,
      output: call.output ?? null,
      duration_ms: safeNumber(call.duration_ms),
      success,
      status: explicitStatus ?? (success === null ? null : success ? 'success' : 'error'),
      latency_ms: safeNumber(call.latency_ms),
      error: typeof call.error === 'string' ? call.error : null,
    }
  })
}

function normalizeEvents(raw: unknown): TraceEvent[] {
  if (!Array.isArray(raw)) return []

  const events = raw.map((item) => {
    const event = asRecord(item)
    const payload = asRecord(event.payload)
    const payloadTraceId = payload.trace_id ?? payload.execution_id
    const occurredAt = typeof payload.occurred_at === 'string'
      ? payload.occurred_at
      : typeof payload.ended_at === 'string'
        ? payload.ended_at
        : null
    return {
      id: typeof event.id === 'string' ? event.id : '',
      trace_id: typeof event.trace_id === 'string'
        ? event.trace_id
        : typeof payloadTraceId === 'string'
          ? payloadTraceId
          : '',
      event_type: typeof event.event_type === 'string' ? event.event_type : 'info',
      latency_ms: safeNumber(event.latency_ms),
      cost_usd: safeNumber(event.cost_usd),
      payload: Object.keys(payload).length > 0 ? payload : null,
      payload_ref: typeof event.payload_ref === 'string' ? event.payload_ref : null,
      created_at: occurredAt ?? (typeof event.created_at === 'string' ? event.created_at : null),
    }
  })

  const completeToolNames = new Set(
    events
      .filter((event) => {
        if (event.event_type !== 'tool_call') return false
        const payload = asRecord(event.payload)
        return typeof payload.tool_call_id === 'string'
          && Object.prototype.hasOwnProperty.call(payload, 'input')
          && Object.prototype.hasOwnProperty.call(payload, 'output')
      })
      .map((event) => asRecord(event.payload).tool_name)
      .filter((name): name is string => typeof name === 'string'),
  )

  return events.filter((event) => {
    if (event.event_type !== 'tool_call') return true
    const payload = asRecord(event.payload)
    const toolName = payload.tool_name
    const isIncomplete = typeof payload.tool_call_id !== 'string'
      || !Object.prototype.hasOwnProperty.call(payload, 'input')
      || !Object.prototype.hasOwnProperty.call(payload, 'output')
    return !(isIncomplete && typeof toolName === 'string' && completeToolNames.has(toolName))
  })
}

export function normalizeTraceDetail(raw: TraceDetail): TraceDetailNormalized {
  const summary = normalizeTraceSummary(raw)
  const data = asRecord(raw.data)
  const events = normalizeEvents(raw.events)

  const completion = events
    .map((event) => asRecord(event.payload))
    .find((payload) => payload.event === 'agent.execution.completed.v1')

  const usage: TraceUsage = {
    inputTokens: safeNumber(data.input_tokens ?? completion?.input_tokens),
    outputTokens: safeNumber(data.output_tokens ?? completion?.output_tokens),
    totalTokens: safeNumber(data.total_tokens ?? completion?.total_tokens),
    costUsd: safeNumber(data.cost_usd ?? completion?.cost_usd ?? raw.total_cost_usd),
  }

  const messageId = summary.messageId
    ?? (typeof completion?.message_id === 'string' ? completion.message_id : null)

  return {
    ...summary,
    messageId,
    usage,
    parsedOutput: data.parsed_output ?? completion?.parsed_output ?? null,
    outputParseError:
      typeof (data.output_parse_error ?? completion?.output_parse_error) === 'string'
        ? String(data.output_parse_error ?? completion?.output_parse_error)
        : null,
    sources: normalizeSources(data.sources ?? completion?.sources),
    toolCalls: normalizeToolCalls(data.tool_calls ?? completion?.tool_calls),
    events,
  }
}
