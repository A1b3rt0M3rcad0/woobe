import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}))

vi.mock('@/lib/api/client', () => client)

import { cancelNetworkExecution } from './api'

describe('Network cancellation API', () => {
  beforeEach(() => {
    client.get.mockReset()
    client.patch.mockReset()
    client.post.mockReset()
  })

  it('deduplicates concurrent Stop requests for the same Network execution', async () => {
    let resolveRequest: ((value: { execution_id: string }) => void) | null = null
    const pending = new Promise<{ execution_id: string }>((resolve) => {
      resolveRequest = resolve
    })
    client.post.mockReturnValueOnce(pending)

    const first = cancelNetworkExecution('execution-1', 'project-1')
    const repeated = cancelNetworkExecution('execution-1', 'project-1')

    expect(repeated).toBe(first)
    expect(client.post).toHaveBeenCalledTimes(1)

    resolveRequest?.({ execution_id: 'execution-1' })
    await first
  })

  it('allows a later idempotent retry after the previous request settled', async () => {
    client.post
      .mockResolvedValueOnce({ execution_id: 'execution-2' })
      .mockResolvedValueOnce({ execution_id: 'execution-2' })

    await cancelNetworkExecution('execution-2', 'project-1')
    await cancelNetworkExecution('execution-2', 'project-1')

    expect(client.post).toHaveBeenCalledTimes(2)
  })

  it('does not deduplicate cancellations belonging to different Projects', async () => {
    client.post.mockResolvedValue({ execution_id: 'execution-shared' })

    await Promise.all([
      cancelNetworkExecution('execution-shared', 'project-a'),
      cancelNetworkExecution('execution-shared', 'project-b'),
    ])

    expect(client.post).toHaveBeenCalledTimes(2)
  })
})
