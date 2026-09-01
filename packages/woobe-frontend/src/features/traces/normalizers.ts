import type {
  FallbackInfo,
  ModelBindingInfo,
  Trace,
  TraceCostStatus,
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

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function pickString(...values: unknown[]): string | null {
  for (const value of values) {
    const found = asString(value)
    if (found) return found
  }
  return null
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

function normalizeCostStatus(value: unknown): TraceCostStatus {
  if (value === 'known' || value === 'partial' || value === 'unknown_tokens' || value === 'unknown_pricing') {
    return value
  }
  return 'unknown'
}

function normalizeBinding(raw: unknown, fallback?: ModelBindingInfo | null): ModelBindingInfo | null {
  const binding = asRecord(raw)
  const result: ModelBindingInfo = {
    provider_model_id: pickString(binding.provider_model_id, fallback?.provider_model_id),
    provider_credential_id: pickString(binding.provider_credential_id, fallback?.provider_credential_id),
    provider: pickString(binding.provider, fallback?.provider),
    model: pickString(binding.model, fallback?.model),
  }
  return Object.values(result).some(Boolean) ? result : null
}

function normalizeFallbackInfo(raw: unknown): FallbackInfo | null {
  const fallback = asRecord(raw)
  if (Object.keys(fallback).length === 0) return null
  return {
    primary_model: typeof fallback.primary_model === 'string' ? fallback.primary_model : null,
    primary_provider: typeof fallback.primary_provider === 'string' ? fallback.primary_provider : null,
    primary_provider_model_id: pickString(fallback.primary_provider_model_id, fallback.provider_model_id),
    primary_credential_id: pickString(fallback.primary_credential_id, fallback.provider_credential_id),
    primary_error: typeof fallback.primary_error === 'string' ? fallback.primary_error : '',
    fallback_model: typeof fallback.fallback_model === 'string' ? fallback.fallback_model : null,
    fallback_provider: typeof fallback.fallback_provider === 'string' ? fallback.fallback_provider : null,
    fallback_provider_model_id: pickString(fallback.fallback_provider_model_id),
    fallback_credential_id: pickString(fallback.fallback_credential_id),
  }
}

export function normalizeTraceSummary(raw: Trace): TraceSummary {
  const data = asRecord(raw.data)
  const providerModelId = pickString(raw.provider_model_id, data.provider_model_id)
  const providerCredentialId = pickString(raw.provider_credential_id, data.provider_credential_id)
  const fallbackProviderModelId = pickString(raw.fallback_provider_model_id, data.fallback_provider_model_id)
  const fallbackCredentialId = pickString(raw.fallback_credential_id, data.fallback_credential_id)
  const modelBinding = normalizeBinding(data.model_binding, {
    provider_model_id: providerModelId,
    provider_credential_id: providerCredentialId,
    provider: pickString(raw.provider, data.provider),
    model: pickString(raw.model, data.model),
  })
  const fallbackModelBinding = normalizeBinding(data.fallback_model_binding, {
    provider_model_id: fallbackProviderModelId,
    provider_credential_id: fallbackCredentialId,
    provider: pickString(data.fallback_provider),
    model: pickString(data.fallback_model),
  })

  return {
    id: raw.id,
    projectId: raw.project_id,
    agentId: raw.agent_id ?? null,
    sessionId: raw.session_id ?? null,
    networkId: raw.network_id ?? null,
    networkExecutionId: raw.network_execution_id ?? null,
    networkSessionId: raw.network_session_id ?? null,
    networkVersionId: raw.network_version_id ?? null,
    messageId: typeof data.message_id === 'string' ? data.message_id : null,
    title: inferTitle(raw),
    status: normalizeStatus(raw.status),
    model: raw.model ?? (typeof data.model === 'string' ? data.model : null),
    provider: raw.provider ?? (typeof data.provider === 'string' ? data.provider : null),
    providerModelId,
    providerCredentialId,
    fallbackProviderModelId,
    fallbackCredentialId,
    modelBinding,
    fallbackModelBinding,
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

const EVENT_BOUNDARY: Record<string, number> = {
  'agent.execution.requested.v1': 10,
  'agent.execution.started.v1': 20,
  'observability.execution.summary.v1': 80,
  'agent.execution.completed.v1': 90,
  'agent.execution.failed.v1': 90,
}

function eventTimestamp(event: TraceEvent): number {
  const value = event.occurred_at ?? event.recorded_at ?? event.created_at
  if (!value) return Number.POSITIVE_INFINITY
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY
}

function normalizeEvents(raw: unknown): TraceEvent[] {
  if (!Array.isArray(raw)) return []

  const events = raw.map((item) => {
    const event = asRecord(item)
    const payload = asRecord(event.payload)
    const payloadTraceId = payload.trace_id ?? payload.execution_id
    const recordedAt = typeof event.created_at === 'string' ? event.created_at : null
    const occurredAt = typeof payload.occurred_at === 'string'
      ? payload.occurred_at
      : typeof payload.ended_at === 'string'
        ? payload.ended_at
        : recordedAt
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
      occurred_at: occurredAt,
      recorded_at: recordedAt,
      sequence: safeNumber(payload.causal_sequence ?? payload.sequence),
      // Backward-compatible display timestamp: operational time wins.
      created_at: occurredAt,
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

  const filtered = events.filter((event) => {
    if (event.event_type !== 'tool_call') return true
    const payload = asRecord(event.payload)
    const toolName = payload.tool_name
    const isIncomplete = typeof payload.tool_call_id !== 'string'
      || !Object.prototype.hasOwnProperty.call(payload, 'input')
      || !Object.prototype.hasOwnProperty.call(payload, 'output')
    return !(isIncomplete && typeof toolName === 'string' && completeToolNames.has(toolName))
  })

  return filtered.sort((left, right) => {
    const leftPayload = asRecord(left.payload)
    const rightPayload = asRecord(right.payload)
    const leftName = typeof leftPayload.event === 'string' ? leftPayload.event : ''
    const rightName = typeof rightPayload.event === 'string' ? rightPayload.event : ''
    const leftBoundary = EVENT_BOUNDARY[leftName] ?? 30
    const rightBoundary = EVENT_BOUNDARY[rightName] ?? 30
    if (leftBoundary !== rightBoundary) return leftBoundary - rightBoundary
    const timeDelta = eventTimestamp(left) - eventTimestamp(right)
    if (timeDelta !== 0) return timeDelta
    const sequenceDelta = (left.sequence ?? 0) - (right.sequence ?? 0)
    if (sequenceDelta !== 0) return sequenceDelta
    return left.id.localeCompare(right.id)
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

  const diagnosticsRaw = asRecord(data.diagnostics ?? completion?.diagnostics)
  const llmWork = safeNumber(diagnosticsRaw.llm_work_latency_ms ?? diagnosticsRaw.llm_runtime_latency_ms)
  const toolWork = safeNumber(diagnosticsRaw.tool_work_latency_ms ?? diagnosticsRaw.tool_call_duration_sum_ms)
  const finalizationWork = safeNumber(diagnosticsRaw.finalization_work_latency_ms ?? diagnosticsRaw.persistence_latency_ms)
  const other = safeNumber(diagnosticsRaw.other_latency_ms ?? diagnosticsRaw.unaccounted_latency_ms)
  const diagnostics = Object.keys(diagnosticsRaw).length > 0
    ? {
        schemaVersion: safeNumber(diagnosticsRaw.schema_version) ?? 1,
        agentRuntimeLatencyMs: safeNumber(diagnosticsRaw.agent_runtime_latency_ms ?? diagnosticsRaw.total_latency_ms),
        llmWorkLatencyMs: llmWork,
        llmRuntimeLatencyMs: llmWork,
        toolWallLatencyMs: safeNumber(diagnosticsRaw.tool_wall_latency_ms),
        toolWorkLatencyMs: toolWork,
        toolCallDurationSumMs: toolWork,
        toolParallelismRatio: safeNumber(diagnosticsRaw.tool_parallelism_ratio),
        toolProviderWorkMs: safeNumber(diagnosticsRaw.tool_provider_work_ms),
        toolRuntimeOverheadMs: safeNumber(diagnosticsRaw.tool_runtime_overhead_ms),
        toolHttpLatencyMs: safeNumber(diagnosticsRaw.tool_http_latency_ms),
        toolOverheadLatencyMs: safeNumber(diagnosticsRaw.tool_overhead_latency_ms),
        prepareLatencyMs: safeNumber(diagnosticsRaw.prepare_latency_ms),
        finalizationWorkLatencyMs: finalizationWork,
        persistenceLatencyMs: finalizationWork,
        otherLatencyMs: other,
        orchestrationLatencyMs: safeNumber(diagnosticsRaw.orchestration_latency_ms),
        unaccountedLatencyMs: other,
        toolSharePercent: safeNumber(diagnosticsRaw.tool_share_percent),
        toolCallCount: safeNumber(diagnosticsRaw.tool_call_count) ?? 0,
        llmCallCount: safeNumber(diagnosticsRaw.llm_call_count) ?? 0,
        successfulToolCalls: safeNumber(diagnosticsRaw.successful_tool_calls) ?? 0,
        failedToolCalls: safeNumber(diagnosticsRaw.failed_tool_calls) ?? 0,
        usageComplete: Boolean(diagnosticsRaw.usage_complete),
        costStatus: normalizeCostStatus(diagnosticsRaw.cost_status),
        costUsd: safeNumber(diagnosticsRaw.cost_usd ?? usage.costUsd),
        sourceCount: safeNumber(diagnosticsRaw.source_count) ?? 0,
        answerLength: safeNumber(diagnosticsRaw.answer_length),
        fallbackUsed: Boolean(diagnosticsRaw.fallback_used),
        structuredOutput: Boolean(diagnosticsRaw.structured_output),
        providerModelId: pickString(diagnosticsRaw.provider_model_id, summary.providerModelId),
        providerCredentialId: pickString(diagnosticsRaw.provider_credential_id, summary.providerCredentialId),
        fallbackProviderModelId: pickString(diagnosticsRaw.fallback_provider_model_id, summary.fallbackProviderModelId),
        fallbackCredentialId: pickString(diagnosticsRaw.fallback_credential_id, summary.fallbackCredentialId),
        notes: Array.isArray(diagnosticsRaw.notes)
          ? diagnosticsRaw.notes.filter((item): item is string => typeof item === 'string')
          : undefined,
      }
    : null

  return {
    ...summary,
    messageId,
    usage,
    diagnostics,
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
