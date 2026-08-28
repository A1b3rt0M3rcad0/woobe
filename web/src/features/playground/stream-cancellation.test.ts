import { describe, expect, it, vi } from 'vitest'

import { createAgentStreamCancellationCoordinator } from './stream-cancellation'

describe('Agent stream cancellation coordinator', () => {
  it('keeps the observer attached and defers cancellation until the Run identity arrives', async () => {
    const requestCancellation = vi.fn(async (_runId: string) => undefined)
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    coordinator.begin()

    expect(coordinator.requestStop()).toBe(true)
    expect(requestCancellation).not.toHaveBeenCalled()

    coordinator.observeRun('run-1')
    await Promise.resolve()

    expect(requestCancellation).toHaveBeenCalledTimes(1)
    expect(requestCancellation).toHaveBeenCalledWith('run-1')
  })

  it('requests cancellation immediately when the active Run identity is already known', async () => {
    const requestCancellation = vi.fn(async (_runId: string) => undefined)
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    coordinator.begin('run-2')

    expect(coordinator.requestStop()).toBe(true)
    await Promise.resolve()

    expect(requestCancellation).toHaveBeenCalledTimes(1)
    expect(requestCancellation).toHaveBeenCalledWith('run-2')
  })

  it('dispatches at most one cancellation request for the same active observer', async () => {
    const requestCancellation = vi.fn(async (_runId: string) => undefined)
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    coordinator.begin('run-3')
    coordinator.requestStop()
    coordinator.requestStop()
    coordinator.observeRun('run-3')
    await Promise.resolve()

    expect(requestCancellation).toHaveBeenCalledTimes(1)
  })

  it('does not leak a pending Stop intent into a later stream', async () => {
    const requestCancellation = vi.fn(async (_runId: string) => undefined)
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    coordinator.begin()
    coordinator.requestStop()
    coordinator.finish()

    coordinator.begin()
    coordinator.observeRun('run-new')
    await Promise.resolve()

    expect(requestCancellation).not.toHaveBeenCalled()
  })

  it('ignores Stop when there is no active observer', () => {
    const requestCancellation = vi.fn(async (_runId: string) => undefined)
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    expect(coordinator.requestStop()).toBe(false)
    expect(requestCancellation).not.toHaveBeenCalled()
  })
})
