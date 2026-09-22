import { runtimeTestEnvelope } from '@/lib/runtime-stream-test-fixtures'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { askStreamV1 } from './stream-client'

function callbacks() {
  return {
    onToken: vi.fn(),
    onSources: vi.fn(),
    onMeta: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn(),
    onCancelled: vi.fn(),
    onTokenRetract: vi.fn(),
    onAgentActivity: vi.fn(),
    onAssistantMessageDelta: vi.fn(),
    onAssistantMessageCompleted: vi.fn(),
    onProtocolError: vi.fn(),
  }
}

function streamResponse(body: string, runId = 'run-1'): Response {
  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'X-Woobe-Run-ID': runId,
    },
  })
}

function runningState(sequence: number, output: string): string {
  return `id: ${sequence}\nevent: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', {
    type: 'run.state',
    run_id: 'run-1',
    sequence,
    status: 'running',
    output,
  }, 'AGENT'))}\n\n`
}

function completedState(sequence: number, output: string): string {
  return `id: ${sequence}\nevent: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', {
    type: 'run.state',
    run_id: 'run-1',
    sequence,
    status: 'completed',
    output,
    result: { answer: output },
  }, 'AGENT'))}\n\n`
}

function durableCancelledState(output: string): string {
  return `event: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', {
    type: 'run.state',
    run_id: 'run-1',
    sequence: null,
    status: 'cancelled',
    output,
    realtime_available: false,
    result: {
      answer: output,
      partial: true,
      cancelled: true,
      reason: 'cancel_requested',
    },
    usage: {
      input_tokens: 8,
      output_tokens: 3,
      total_tokens: 11,
    },
  }, 'AGENT'))}\n\n`
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('Agent runtime stream reattach', () => {
  it('switches to canonical GET after transport EOF once Run id is known', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(streamResponse(runningState(3, 'partial')))
      .mockResolvedValueOnce(streamResponse(completedState(7, 'final answer')))
    vi.stubGlobal('fetch', fetchMock)
    const handlers = callbacks()

    const execution = askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'hello',
    }, handlers)
    await vi.runAllTimersAsync()
    await execution

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('POST')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/runtime/runs/run-1/stream')
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe('GET')
    expect(handlers.onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'final answer' }))
  })

  it('rejects sequence gaps and reconciles through run.state instead of applying skipped delta', async () => {
    vi.useFakeTimers()
    const skipped = `id: 5\nevent: token\ndata: ${JSON.stringify(runtimeTestEnvelope('token', {
      type: 'token',
      run_id: 'run-1',
      sequence: 5,
      content: 'MUST-NOT-APPLY',
      visibility: 'assistant',
      channel: 'final',
      phase: 'final_response_generation',
    }, 'AGENT'))}\n\n`
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(streamResponse(`${runningState(3, 'partial')}${skipped}`))
      .mockResolvedValueOnce(streamResponse(completedState(8, 'reconciled answer')))
    vi.stubGlobal('fetch', fetchMock)
    const handlers = callbacks()

    const execution = askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'hello',
    }, handlers)
    await vi.runAllTimersAsync()
    await execution

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe('GET')
    expect(handlers.onProtocolError).toHaveBeenCalledWith(
      'Runtime stream sequence gap: expected 4, received 5',
      expect.any(Object),
    )
    expect(handlers.onToken).not.toHaveBeenCalledWith(
      expect.objectContaining({ content: 'MUST-NOT-APPLY' }),
    )
    expect(handlers.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ answer: 'reconciled answer' }),
    )
  })

  it('accepts an authoritative durable cancelled snapshot without a hot sequence cursor', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(streamResponse(runningState(5, 'partial')))
      .mockResolvedValueOnce(streamResponse(durableCancelledState('partial answer')))
    vi.stubGlobal('fetch', fetchMock)
    const handlers = callbacks()

    const execution = askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'hello',
    }, handlers)
    await vi.runAllTimersAsync()
    await execution

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe('GET')
    expect(handlers.onProtocolError).not.toHaveBeenCalled()
    expect(handlers.onError).not.toHaveBeenCalled()
    expect(handlers.onCancelled).toHaveBeenCalledWith(expect.objectContaining({
      run_id: 'run-1',
      status: 'cancelled',
      sequence: null,
      output: 'partial answer',
      realtime_available: false,
    }))
  })
})

describe('Agent runtime terminal response', () => {
  it('preserves the effective provider in the terminal response contract', async () => {
    const done = `event: done\ndata: ${JSON.stringify(runtimeTestEnvelope('done', {
      type: 'done',
      run_id: 'run-1',
      answer: 'provider answer',
      provider: 'openai',
      model: 'gpt-test',
    }, 'AGENT'))}\n\n`
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse(done)))
    const handlers = callbacks()

    await askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'hello',
    }, handlers)

    expect(handlers.onDone).toHaveBeenCalledWith(expect.objectContaining({
      answer: 'provider answer',
      provider: 'openai',
      model: 'gpt-test',
    }))
  })
})


describe('Strategy-neutral runtime presentation', () => {
  it('accepts public assistant output from a Strategy-specific phase', async () => {
    const body = [
      `event: token\ndata: ${JSON.stringify(runtimeTestEnvelope('token', {
        type: 'token',
        run_id: 'run-1',
        content: 'evidence-backed answer',
        visibility: 'assistant',
        channel: 'final',
        phase: 'conclusion',
      }, 'AGENT'))}\n\n`,
      `event: done\ndata: ${JSON.stringify(runtimeTestEnvelope('done', {
        type: 'done',
        run_id: 'run-1',
        answer: 'evidence-backed answer',
      }, 'AGENT'))}\n\n`,
    ].join('')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse(body)))
    const handlers = callbacks()

    await askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'investigate',
    }, handlers)

    expect(handlers.onToken).toHaveBeenCalledWith(expect.objectContaining({
      content: 'evidence-backed answer',
      phase: 'conclusion',
    }))
  })

  it('preserves backend activity message for Strategy-specific phases', async () => {
    const body = [
      `event: agent_activity\ndata: ${JSON.stringify(runtimeTestEnvelope('agent_activity', {
        type: 'agent_activity',
        run_id: 'run-1',
        status: 'thinking',
        phase: 'critical_review',
        message: 'Critical review...',
      }, 'AGENT'))}\n\n`,
      `event: done\ndata: ${JSON.stringify(runtimeTestEnvelope('done', {
        type: 'done',
        run_id: 'run-1',
        answer: 'done',
      }, 'AGENT'))}\n\n`,
    ].join('')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse(body)))
    const handlers = callbacks()

    await askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'investigate',
    }, handlers)

    expect(handlers.onAgentActivity).toHaveBeenCalledWith(expect.objectContaining({
      status: 'thinking',
      phase: 'critical_review',
      message: 'Critical review...',
    }))
  })
})


describe('Intermediate Assistant messages', () => {
  it('dispatches intermediate deltas separately from final output tokens', async () => {
    const body = [
      `event: assistant_message_delta\ndata: ${JSON.stringify(runtimeTestEnvelope('assistant_message_delta', {
        type: 'assistant_message_delta',
        run_id: 'run-1',
        message_id: 'msg-progress',
        content: 'I found one cause. ',
        phase: 'progress_update',
        output_mode: 'intermediate',
      }, 'AGENT'))}\n\n`,
      `event: assistant_message_delta\ndata: ${JSON.stringify(runtimeTestEnvelope('assistant_message_delta', {
        type: 'assistant_message_delta',
        run_id: 'run-1',
        message_id: 'msg-progress',
        content: 'I will verify it.',
        phase: 'progress_update',
        output_mode: 'intermediate',
      }, 'AGENT'))}\n\n`,
      `event: assistant_message_completed\ndata: ${JSON.stringify(runtimeTestEnvelope('assistant_message_completed', {
        type: 'assistant_message_completed',
        run_id: 'run-1',
        message_id: 'msg-progress',
        content: 'I found one cause. I will verify it.',
        phase: 'progress_update',
        output_mode: 'intermediate',
      }, 'AGENT'))}\n\n`,
      `event: done\ndata: ${JSON.stringify(runtimeTestEnvelope('done', {
        type: 'done',
        run_id: 'run-1',
        answer: 'Final answer',
      }, 'AGENT'))}\n\n`,
    ].join('')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse(body)))
    const handlers = callbacks()

    await askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'investigate',
    }, handlers)

    expect(handlers.onAssistantMessageDelta).toHaveBeenCalledTimes(2)
    expect(handlers.onAssistantMessageDelta).toHaveBeenLastCalledWith(
      expect.objectContaining({
        message_id: 'msg-progress',
        content: 'I will verify it.',
        phase: 'progress_update',
        output_mode: 'intermediate',
      }),
    )
    expect(handlers.onAssistantMessageCompleted).toHaveBeenCalledWith(
      expect.objectContaining({
        message_id: 'msg-progress',
        content: 'I found one cause. I will verify it.',
      }),
    )
    expect(handlers.onToken).not.toHaveBeenCalled()
    expect(handlers.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ answer: 'Final answer' }),
    )
  })

  it('restores completed intermediate messages from run.state', async () => {
    const state = `event: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', {
      type: 'run.state',
      run_id: 'run-1',
      sequence: null,
      status: 'completed',
      output: 'Final answer',
      realtime_available: false,
      messages: [{
        message_id: 'msg-progress',
        content: 'Progress already persisted.',
        phase: 'progress_update',
        output_mode: 'intermediate',
        status: 'completed',
      }],
      result: { answer: 'Final answer' },
    }, 'AGENT'))}\n\n`
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse(state)))
    const handlers = callbacks()

    await askStreamV1({
      project_id: 'project-1',
      agent_id: 'agent-1',
      message: 'investigate',
    }, handlers)

    expect(handlers.onAssistantMessageCompleted).toHaveBeenCalledWith(
      expect.objectContaining({
        message_id: 'msg-progress',
        content: 'Progress already persisted.',
        phase: 'progress_update',
      }),
    )
    expect(handlers.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ answer: 'Final answer' }),
    )
  })
})
