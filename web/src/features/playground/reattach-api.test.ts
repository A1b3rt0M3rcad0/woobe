import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

import { post } from '@/lib/api/client'
import { cancelAgentRun } from './reattach-api'

describe('cancelAgentRun', () => {
  const postMock = vi.mocked(post)

  beforeEach(() => {
    postMock.mockReset()
  })

  it('deduplicates concurrent cancellation requests for the same Run', async () => {
    let release!: () => void
    postMock.mockReturnValue(new Promise<void>((resolve) => {
      release = resolve
    }))

    const first = cancelAgentRun('run-1')
    const second = cancelAgentRun('run-1')

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(postMock).toHaveBeenCalledWith('/runtime/runs/run-1/cancel', {})

    release()
    await Promise.all([first, second])
  })

  it('allows a later retry after the previous cancellation request settles', async () => {
    postMock.mockResolvedValue(undefined)

    await cancelAgentRun('run-2')
    await cancelAgentRun('run-2')

    expect(postMock).toHaveBeenCalledTimes(2)
  })
})
