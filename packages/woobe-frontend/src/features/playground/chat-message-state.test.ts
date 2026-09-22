import { describe, expect, it } from 'vitest'

import type { AssistantMessageInfo, ChatMessage } from '@/features/playground/types'
import {
  updateTerminalAssistantMessage,
  upsertIntermediateAssistantMessage,
} from './chat-message-state'

function intermediate(messageId: string, content: string): AssistantMessageInfo {
  return {
    message_id: messageId,
    content,
    output_mode: 'intermediate',
    phase: 'user_update',
  }
}

describe('playground assistant message state', () => {
  it('keeps intermediate messages before the terminal placeholder', () => {
    const base: ChatMessage[] = [
      { role: 'user', content: 'research this' },
      {
        role: 'assistant',
        content: '',
        run_id: 'run-1',
        output_mode: 'final',
        activity: { status: 'working', message: 'Working...' },
      },
    ]

    const first = upsertIntermediateAssistantMessage(
      base,
      intermediate('message-1', 'Vou procurar.'),
      'run-1',
      false,
    )
    const second = upsertIntermediateAssistantMessage(
      first,
      intermediate('message-2', 'Achei. Vou analisar melhor.'),
      'run-1',
      false,
    )
    const completed = updateTerminalAssistantMessage(second, (message) => ({
      ...message,
      message_id: 'message-3',
      content: 'Isso quer dizer que...',
      output_mode: 'final',
      activity: null,
    }))

    expect(completed.map((message) => message.content)).toEqual([
      'research this',
      'Vou procurar.',
      'Achei. Vou analisar melhor.',
      'Isso quer dizer que...',
    ])
    expect(completed.map((message) => message.message_id ?? null)).toEqual([
      null,
      'message-1',
      'message-2',
      'message-3',
    ])
  })

  it('updates an intermediate stream by message id without touching the final message', () => {
    const base: ChatMessage[] = [
      { role: 'user', content: 'research this' },
      { role: 'assistant', content: '', run_id: 'run-1', output_mode: 'final' },
    ]

    const delta = upsertIntermediateAssistantMessage(
      base,
      intermediate('message-1', 'Vou '),
      'run-1',
      true,
    )
    const delta2 = upsertIntermediateAssistantMessage(
      delta,
      intermediate('message-1', 'procurar.'),
      'run-1',
      true,
    )
    const completed = upsertIntermediateAssistantMessage(
      delta2,
      intermediate('message-1', 'Vou procurar.'),
      'run-1',
      false,
    )

    expect(completed[1]).toMatchObject({
      message_id: 'message-1',
      content: 'Vou procurar.',
      output_mode: 'intermediate',
      run_id: 'run-1',
    })
    expect(completed[2]).toMatchObject({
      content: '',
      output_mode: 'final',
      run_id: 'run-1',
    })
  })

  it('never lets terminal activity overwrite the latest intermediate message', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'research this' },
      {
        role: 'assistant',
        content: 'Vou procurar.',
        message_id: 'message-1',
        output_mode: 'intermediate',
      },
      {
        role: 'assistant',
        content: '',
        message_id: 'message-final',
        output_mode: 'final',
      },
    ]

    const updated = updateTerminalAssistantMessage(messages, (message) => ({
      ...message,
      activity: { status: 'calling_tool', message: 'Calling tool...' },
    }))

    expect(updated[1].activity).toBeUndefined()
    expect(updated[2].activity?.message).toBe('Calling tool...')
  })
})
