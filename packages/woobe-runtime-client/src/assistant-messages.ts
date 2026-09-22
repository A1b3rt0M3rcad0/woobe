import type {
  ParsedRuntimeFrame,
  RuntimeAssistantMessage,
} from './types'

function assistantMessageFromValue(value: unknown): RuntimeAssistantMessage | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const payload = value as Record<string, unknown>
  if (
    typeof payload.message_id !== 'string'
    || !payload.message_id
    || typeof payload.content !== 'string'
    || payload.output_mode !== 'intermediate'
  ) {
    return null
  }

  return {
    message_id: payload.message_id,
    content: payload.content,
    output_mode: 'intermediate',
    phase: typeof payload.phase === 'string' ? payload.phase : null,
    provider: typeof payload.provider === 'string' ? payload.provider : null,
    model: typeof payload.model === 'string' ? payload.model : null,
    partial: typeof payload.partial === 'boolean' ? payload.partial : null,
    status: typeof payload.status === 'string' ? payload.status : null,
    completed_at: typeof payload.completed_at === 'string' ? payload.completed_at : null,
  }
}

export function runtimeAssistantMessage(
  frame: ParsedRuntimeFrame,
): RuntimeAssistantMessage | null {
  if (
    frame.eventType !== 'assistant_message_delta'
    && frame.eventType !== 'assistant_message_completed'
  ) {
    return null
  }
  return assistantMessageFromValue(frame.payload)
}

export function runtimeStateAssistantMessages(
  frame: ParsedRuntimeFrame,
): RuntimeAssistantMessage[] {
  if (frame.eventType !== 'run.state') return []
  const messages = frame.payload.messages
  if (!Array.isArray(messages)) return []

  const typed: RuntimeAssistantMessage[] = []
  for (const message of messages) {
    const parsed = assistantMessageFromValue(message)
    if (parsed !== null) typed.push(parsed)
  }
  return typed
}

export function runtimeAssistantMessages(
  frame: ParsedRuntimeFrame,
): RuntimeAssistantMessage[] {
  const message = runtimeAssistantMessage(frame)
  return message === null ? runtimeStateAssistantMessages(frame) : [message]
}
