import type {
  AssistantMessageInfo,
  ChatMessage,
} from '@/features/playground/types'

export function updateTerminalAssistantMessage(
  messages: ChatMessage[],
  updater: (message: ChatMessage) => ChatMessage,
): ChatMessage[] {
  let index = -1
  for (let cursor = messages.length - 1; cursor >= 0; cursor -= 1) {
    const message = messages[cursor]
    if (message.role === 'assistant' && message.output_mode !== 'intermediate') {
      index = cursor
      break
    }
  }
  if (index < 0) return messages

  const updated = [...messages]
  updated[index] = updater(updated[index])
  return updated
}

export function upsertIntermediateAssistantMessage(
  messages: ChatMessage[],
  info: AssistantMessageInfo,
  runId: string | null,
  append: boolean,
): ChatMessage[] {
  const existingIndex = messages.findIndex((message) => (
    message.role === 'assistant' && message.message_id === info.message_id
  ))
  if (existingIndex >= 0) {
    const updated = [...messages]
    const existing = updated[existingIndex]
    updated[existingIndex] = {
      ...existing,
      content: append ? existing.content + info.content : info.content,
      run_id: existing.run_id ?? runId,
      phase: info.phase ?? existing.phase ?? null,
      output_mode: 'intermediate',
      partial: info.partial ?? existing.partial ?? null,
      model: info.model ?? existing.model ?? null,
      provider: info.provider ?? existing.provider ?? null,
      activity: null,
    }
    return updated
  }

  const message: ChatMessage = {
    role: 'assistant',
    content: info.content,
    message_id: info.message_id,
    run_id: runId,
    phase: info.phase ?? null,
    output_mode: 'intermediate',
    partial: info.partial ?? null,
    model: info.model ?? null,
    provider: info.provider ?? null,
    activity: null,
  }

  let terminalIndex = -1
  for (let cursor = messages.length - 1; cursor >= 0; cursor -= 1) {
    const candidate = messages[cursor]
    if (candidate.role !== 'assistant' || candidate.output_mode === 'intermediate') continue
    if (runId && candidate.run_id && candidate.run_id !== runId) continue
    terminalIndex = cursor
    break
  }

  if (terminalIndex < 0) return [...messages, message]
  return [
    ...messages.slice(0, terminalIndex),
    message,
    ...messages.slice(terminalIndex),
  ]
}


export function applyCompletedAssistantMessage(
  messages: ChatMessage[],
  info: AssistantMessageInfo,
  runId: string | null,
): ChatMessage[] {
  if (info.output_mode === 'intermediate') {
    return upsertIntermediateAssistantMessage(messages, info, runId, false)
  }

  return updateTerminalAssistantMessage(messages, (message) => ({
    ...message,
    content: info.content,
    message_id: info.message_id,
    run_id: message.run_id ?? runId,
    phase: info.phase ?? message.phase ?? null,
    output_mode: 'final',
    partial: info.partial ?? message.partial ?? null,
    model: info.model ?? message.model ?? null,
    provider: info.provider ?? message.provider ?? null,
    activity: null,
  }))
}
