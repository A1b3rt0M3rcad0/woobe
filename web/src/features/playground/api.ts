import { post, get, getCsrfHeaders, refreshAuthSession } from '@/lib/api/client'
import type { CreateSessionRequest, Session, SessionListItem, SessionListPage, AskRequest, AskResponse, Message, SourceInfo, ToolCallInfo, FallbackEventInfo } from './types'

export interface CreateAskJobRequest {
  project_id: string
  agent_id: string
  message: string
  session_id?: string | null
}

export interface AskJobResult {
  job_id: string
  status: string
  result?: AskResponse | null
  error?: string | null
  trace_id?: string | null
  created_at?: string | null
  started_at?: string | null
  completed_at?: string | null
}

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function normalizeResponse(response: Record<string, unknown>): AskResponse {
  const { type: _type, ...rest } = response
  return {
    answer: (rest.answer as string) ?? '',
    session_id: (rest.session_id as string) ?? null,
    message_id: (rest.message_id as string) ?? null,
    usage: rest.usage
      ? {
          input_tokens: (rest.usage as Record<string, unknown>).input_tokens as number ?? null,
          output_tokens: (rest.usage as Record<string, unknown>).output_tokens as number ?? null,
          total_tokens: (rest.usage as Record<string, unknown>).total_tokens as number ?? null,
          cost_usd: (rest.usage as Record<string, unknown>).cost_usd as number ?? null,
        }
      : { input_tokens: null, output_tokens: null, total_tokens: null, cost_usd: null },
    sources: (rest.sources as SourceInfo[]) ?? [],
    tool_calls: (rest.tool_calls as ToolCallInfo[]) ?? [],
    trace_id: (rest.trace_id as string) ?? null,
    model: (rest.model as string) ?? null,
    provider: (rest.provider as string) ?? null,
    provider_model_id: asString(rest.provider_model_id),
    provider_credential_id: asString(rest.provider_credential_id),
    fallback_provider_model_id: asString(rest.fallback_provider_model_id),
    fallback_credential_id: asString(rest.fallback_credential_id),
    fallback_used: (rest.fallback_used as boolean) ?? false,
    fallback_info: (rest.fallback_info ?? null) as unknown as AskResponse['fallback_info'],
    latency_ms: (rest.latency_ms as number) ?? null,
    parsed_output: (rest.parsed_output as Record<string, unknown>) ?? null,
    output_parse_error: (rest.output_parse_error as string) ?? null,
    execution_events: (rest.execution_events as AskResponse['execution_events']) ?? [],
    diagnostics: (rest.diagnostics as AskResponse['diagnostics']) ?? null,
  }
}

function streamToolCallInfo(parsed: Record<string, unknown>): ToolCallInfo {
  return {
    tool_call_id: asString(parsed.tool_call_id),
    tool_name: asString(parsed.tool_name) ?? '',
    input: parsed.input ?? null,
    output: parsed.output ?? null,
    duration_ms: asNumber(parsed.duration_ms) ?? undefined,
    success: asBoolean(parsed.success),
    status: asString(parsed.status),
    latency_ms: asNumber(parsed.http_latency_ms) ?? asNumber(parsed.latency_ms),
    error: asString(parsed.error),
  }
}

export async function createSession(data: CreateSessionRequest): Promise<Session> {
  return post<Session>('/runtime/sessions', data)
}

export async function ask(data: AskRequest): Promise<AskResponse> {
  const response = await post<Record<string, unknown>>('/runtime/ask', data)
  return normalizeResponse(response)
}

export async function getAgentSessions(
  agentId: string,
  projectId: string,
  params: { limit?: number; cursor?: string | null } = {},
): Promise<SessionListPage> {
  const response = await get<SessionListPage | SessionListItem[]>(`/runtime/agents/${agentId}/sessions`, {
    params: {
      project_id: projectId,
      limit: params.limit,
      cursor: params.cursor ?? undefined,
    },
  })

  if (Array.isArray(response)) {
    return {
      items: response,
      next_cursor: null,
      has_next: false,
    }
  }

  return response
}

export async function getSessionMessages(sessionId: string, params?: { offset?: number; limit?: number }): Promise<Message[]> {
  return get<Message[]>(`/runtime/sessions/${sessionId}/messages`, { params: params as Record<string, string | number | undefined> })
}

export interface StreamCallbacks {
  onToken: (content: string) => void
  onSources: (sources: SourceInfo[]) => void
  onMeta: (meta: { session_id?: string | null; trace_id?: string | null }) => void
  onDone: (response: Partial<AskResponse>) => void
  onError: (error: Error) => void
  onFallback?: (info: FallbackEventInfo) => void
  onToolCall?: (info: ToolCallInfo) => void
}

export async function createAskJob(data: CreateAskJobRequest): Promise<{ job_id: string; status: string }> {
  return post<{ job_id: string; status: string }>('/runtime/ask/jobs', data)
}

export async function getAskJobResult(jobId: string): Promise<AskJobResult> {
  return get<AskJobResult>(`/runtime/ask/jobs/${jobId}`)
}

async function askStreamRequest(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal: AbortSignal | undefined,
  hasRetriedAuth: boolean,
): Promise<void> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getCsrfHeaders('POST'),
  }

  const response = await fetch(`${BASE_URL}/runtime/ask/stream`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(data),
    signal,
  })

  if (response.status === 401 && !hasRetriedAuth) {
    try {
      await refreshAuthSession()
      return askStreamRequest(data, callbacks, signal, true)
    } catch {
      throw new Error('Authentication session expired')
    }
  }

  if (!response.ok) {
    let errorMsg = `Stream request failed (${response.status})`
    try {
      const errBody = await response.json()
      errorMsg = errBody?.message || errorMsg
    } catch {
      // ignore parse error
    }
    throw new Error(errorMsg)
  }

  if (!response.body) {
    throw new Error('Streaming response body is unavailable')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue

      try {
        const parsed = JSON.parse(trimmed.slice(6))
        const type = parsed.type

        switch (type) {
          case 'token':
            callbacks.onToken(parsed.content ?? '')
            break
          case 'sources':
            callbacks.onSources(parsed.sources ?? [])
            break
          case 'meta':
            callbacks.onMeta({
              session_id: parsed.session_id ?? null,
              trace_id: parsed.trace_id ?? null,
            })
            break
          case 'done':
            callbacks.onDone(normalizeResponse(parsed))
            break
          case 'error':
            callbacks.onError(new Error(parsed.message ?? 'Stream error'))
            return
          case 'fallback':
            callbacks.onFallback?.({
              primary_provider: parsed.primary_provider ?? '',
              primary_model: parsed.primary_model ?? '',
              fallback_provider: parsed.fallback_provider ?? '',
              fallback_model: parsed.fallback_model ?? '',
              error: parsed.error ?? 'Unknown error',
            })
            break
          case 'tool_call':
          case 'tool_call_started':
          case 'tool_call_completed':
            callbacks.onToolCall?.(streamToolCallInfo(parsed))
            break
        }
      } catch (e) {
        console.warn('[askStream] Failed to parse SSE line:', line, e)
      }
    }
  }
}

export async function askStream(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  return askStreamRequest(data, callbacks, signal, false)
}