import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { NetworkTurnDetails } from './NetworkExecutionTree'
import type { NetworkAgentInvocation, NetworkTurn } from './networkChatExecution'

function artifact(path: string, id: string) {
  return {
    schema_version: '1' as const,
    ref: { artifact_id: id, revision_id: `revision-${id}` },
    path,
    content_type: 'application/pdf',
    size_bytes: 12,
    sha256: 'a'.repeat(64),
    status: 'available' as const,
    source_refs: [],
  }
}

const root: NetworkAgentInvocation = {
  spanId: 'root-span', runId: null, parentSpanId: null, sequence: 1, nodeId: 'root-node' as never,
  agentId: 'root-agent', agentName: 'Entry Agent', agentSessionId: null, contextState: 'created',
  previousInvocationCount: 0, childTraceId: null, source: 'draft', version: 'current', status: 'success',
  outputArtifacts: [artifact('final/answer.pdf', 'root-artifact')], tools: [], sources: [],
  children: [{
    spanId: 'child-span', runId: null, parentSpanId: 'root-span', sequence: 2, nodeId: 'writer-node' as never,
    agentId: 'writer-agent', agentName: 'Report Writer', agentSessionId: null, contextState: 'created',
    previousInvocationCount: 0, childTraceId: null, source: 'draft', version: 'current', status: 'success',
    outputArtifacts: [artifact('draft/report.pdf', 'child-artifact')], tools: [], sources: [], children: [],
  }],
}

const turn = {
  id: 'turn-1', user: 'Write a report', answer: 'Done', provider: 'test', model: 'fixture', usage: null,
  execution: { id: 'execution-1', traceId: null, status: 'success', environment: 'draft', startedAt: '', durationMs: 1, costUsd: null, path: [], root },
} as NetworkTurn

describe('Network node artifact outputs', () => {
  it('attributes committed files to each producing Node and uses the scoped workspace for download', () => {
    const html = renderToStaticMarkup(<MemoryRouter><NetworkTurnDetails
      turn={turn}
      onSelectAgent={vi.fn()}
      artifactContext={{ projectId: 'project-1', environment: 'draft', workspaceId: 'artifact-workspace-1', accountWorkspaceId: 'account-workspace-1' }}
    /></MemoryRouter>)

    expect(html).toContain('Artifacts produced by Entry Agent')
    expect(html).toContain('Artifacts produced by Report Writer')
    expect(html).toContain('final/answer.pdf')
    expect(html).toContain('draft/report.pdf')
  })

  it('does not render artifact metadata when the active runtime has no read scope', () => {
    const html = renderToStaticMarkup(<NetworkTurnDetails turn={turn} onSelectAgent={vi.fn()} />)
    expect(html).not.toContain('final/answer.pdf')
    expect(html).not.toContain('draft/report.pdf')
  })
})
