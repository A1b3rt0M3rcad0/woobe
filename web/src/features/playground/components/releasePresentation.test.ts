import { describe, expect, it } from 'vitest'

import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import {
  newestProductionChanges,
  promotableReleases,
} from './releasePresentation'

function release(overrides: Partial<AgentRelease>): AgentRelease {
  return {
    id: 'release-default',
    project_id: 'project-1',
    agent_id: 'agent-1',
    version: 'v1.0.0',
    status: 'released',
    snapshot_kind: 'release',
    ...overrides,
  }
}

function activation(overrides: Partial<AgentReleaseActivation>): AgentReleaseActivation {
  return {
    id: 'activation-default',
    project_id: 'project-1',
    agent_id: 'agent-1',
    release_id: 'release-default',
    action: 'deploy',
    ...overrides,
  }
}

describe('Agent release presentation', () => {
  it('keeps only non-Production immutable Releases and orders newest first', () => {
    const result = promotableReleases([
      release({ id: 'staging', version: 'staging-r2', status: 'staging', snapshot_kind: 'staging', created_at: '2026-07-20T12:00:00Z' }),
      release({ id: 'production', version: 'v3.0.0', status: 'production', created_at: '2026-07-20T14:00:00Z' }),
      release({ id: 'older', version: 'v1.0.0', created_at: '2026-07-18T14:00:00Z' }),
      release({ id: 'newer', version: 'v2.0.0', status: 'rolled_back', created_at: '2026-07-19T14:00:00Z' }),
    ])

    expect(result.map((item) => item.id)).toEqual(['newer', 'older'])
  })

  it('orders Production changes from newest to oldest', () => {
    const result = newestProductionChanges([
      activation({ id: 'older', created_at: '2026-07-18T14:00:00Z' }),
      activation({ id: 'newest', created_at: '2026-07-20T14:00:00Z' }),
      activation({ id: 'middle', created_at: '2026-07-19T14:00:00Z' }),
    ])

    expect(result.map((item) => item.id)).toEqual(['newest', 'middle', 'older'])
  })
})
