import { describe, expect, it } from 'vitest'
import { normalizeTraceDetail } from './normalizers'
import type { TraceDetail } from './types'

function detail(overrides: Partial<TraceDetail> = {}): TraceDetail {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    project_id: '00000000-0000-0000-0000-000000000002',
    status: 'completed',
    data: {},
    events: [],
    ...overrides,
  }
}

describe('normalizeTraceDetail diagnostics', () => {
  it('normalizes diagnostics v5 wall/work semantics', () => {
    const normalized = normalizeTraceDetail(detail({
      data: {
        diagnostics: {
          schema_version: 5,
          agent_runtime_latency_ms: 1000,
          llm_work_latency_ms: 500,
          tool_wall_latency_ms: 250,
          tool_work_latency_ms: 350,
          tool_parallelism_ratio: 1.4,
          finalization_work_latency_ms: 50,
          other_latency_ms: 100,
          orchestration_latency_ms: null,
          tool_call_count: 2,
          llm_call_count: 2,
          successful_tool_calls: 2,
          failed_tool_calls: 0,
          usage_complete: true,
          cost_status: 'known',
          cost_usd: 0.001,
        },
      },
    }))

    expect(normalized.diagnostics?.schemaVersion).toBe(5)
    expect(normalized.diagnostics?.llmWorkLatencyMs).toBe(500)
    expect(normalized.diagnostics?.toolWallLatencyMs).toBe(250)
    expect(normalized.diagnostics?.toolWorkLatencyMs).toBe(350)
    expect(normalized.diagnostics?.toolParallelismRatio).toBe(1.4)
    expect(normalized.diagnostics?.finalizationWorkLatencyMs).toBe(50)
    expect(normalized.diagnostics?.otherLatencyMs).toBe(100)
    expect(normalized.diagnostics?.orchestrationLatencyMs).toBeNull()
    expect(normalized.diagnostics?.costUsd).toBe(0.001)
  })

  it('keeps v4 aliases readable as the v5 view model', () => {
    const normalized = normalizeTraceDetail(detail({
      data: {
        diagnostics: {
          schema_version: 4,
          total_latency_ms: 1000,
          llm_runtime_latency_ms: 500,
          tool_wall_latency_ms: 250,
          tool_call_duration_sum_ms: 350,
          persistence_latency_ms: 50,
          unaccounted_latency_ms: 100,
          cost_status: 'unknown',
        },
      },
    }))

    expect(normalized.diagnostics?.agentRuntimeLatencyMs).toBe(1000)
    expect(normalized.diagnostics?.llmWorkLatencyMs).toBe(500)
    expect(normalized.diagnostics?.toolWorkLatencyMs).toBe(350)
    expect(normalized.diagnostics?.finalizationWorkLatencyMs).toBe(50)
    expect(normalized.diagnostics?.otherLatencyMs).toBe(100)
    expect(normalized.diagnostics?.costStatus).toBe('unknown')
  })

  it('orders operations by occurred_at while retaining recorded_at', () => {
    const normalized = normalizeTraceDetail(detail({
      events: [
        {
          id: 'event-llm',
          trace_id: '00000000-0000-0000-0000-000000000001',
          event_type: 'llm_call',
          created_at: '2026-08-25T02:13:20Z',
          payload: {
            event: 'agent.execution.llm_completed.v1',
            call_id: 'llm-final',
            occurred_at: '2026-08-25T02:13:10Z',
          },
        },
        {
          id: 'event-tool',
          trace_id: '00000000-0000-0000-0000-000000000001',
          event_type: 'tool_call',
          created_at: '2026-08-25T02:13:21Z',
          payload: {
            event: 'agent.execution.tool_completed.v1',
            tool_call_id: 'tool-before-final',
            input: {},
            output: {},
            occurred_at: '2026-08-25T02:13:05Z',
          },
        },
      ],
    }))

    expect(normalized.events.map((event) => event.id)).toEqual([
      'event-tool',
      'event-llm',
    ])
    expect(normalized.events[0].occurred_at).toBe('2026-08-25T02:13:05Z')
    expect(normalized.events[0].recorded_at).toBe('2026-08-25T02:13:21Z')
    expect(normalized.events[0].created_at).toBe('2026-08-25T02:13:05Z')
  })

  it('uses causal sequence to break identical operation timestamps', () => {
    const normalized = normalizeTraceDetail(detail({
      events: [
        {
          id: 'event-second',
          trace_id: '00000000-0000-0000-0000-000000000001',
          event_type: 'tool_call',
          payload: {
            event: 'agent.execution.tool_completed.v1',
            tool_call_id: 'second',
            input: {},
            output: {},
            occurred_at: '2026-08-25T02:13:05Z',
            causal_sequence: 2,
          },
        },
        {
          id: 'event-first',
          trace_id: '00000000-0000-0000-0000-000000000001',
          event_type: 'tool_call',
          payload: {
            event: 'agent.execution.tool_completed.v1',
            tool_call_id: 'first',
            input: {},
            output: {},
            occurred_at: '2026-08-25T02:13:05Z',
            causal_sequence: 1,
          },
        },
      ],
    }))

    expect(normalized.events.map((event) => event.id)).toEqual([
      'event-first',
      'event-second',
    ])
  })
})
