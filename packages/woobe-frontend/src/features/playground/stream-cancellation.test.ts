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

  it('dispatches at most one cancellation request while the request is pending', async () => {
    let resolveCancellation!: () => void
    const requestCancellation = vi.fn(() => new Promise<void>((resolve) => { resolveCancellation = resolve }))
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    coordinator.begin('run-3')
    expect(coordinator.requestStop()).toBe(true)
    expect(coordinator.requestStop()).toBe(false)
    coordinator.observeRun('run-3')

    expect(requestCancellation).toHaveBeenCalledTimes(1)
    resolveCancellation()
    await Promise.resolve()
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

  it('reports dispatch and confirmation for a known Run', async () => {
    const requestCancellation = vi.fn(async (_runId: string) => undefined)
    const onDispatch = vi.fn()
    const onConfirmed = vi.fn()
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation, {
      onDispatch,
      onConfirmed,
    })

    coordinator.begin('run-confirmed')
    coordinator.requestStop()
    await Promise.resolve()
    await Promise.resolve()

    expect(onDispatch).toHaveBeenCalledWith('run-confirmed')
    expect(onConfirmed).toHaveBeenCalledWith('run-confirmed')
  })

  it('reports cancellation request failures and allows a retry on the same observer', async () => {
    const failure = new Error('cancel request failed')
    const requestCancellation = vi.fn()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(undefined)
    const onError = vi.fn()
    const onConfirmed = vi.fn()
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation, { onError, onConfirmed })

    coordinator.begin('run-failed')
    expect(coordinator.requestStop()).toBe(true)
    await Promise.resolve()
    await Promise.resolve()

    expect(onError).toHaveBeenCalledWith('run-failed', failure)
    expect(coordinator.requestStop()).toBe(true)
    await Promise.resolve()
    await Promise.resolve()

    expect(requestCancellation).toHaveBeenCalledTimes(2)
    expect(onConfirmed).toHaveBeenCalledWith('run-failed')
  })

  it('reports a deferred cancellation failure after the Run identity arrives and permits retry', async () => {
    const requestCancellation = vi.fn()
      .mockRejectedValueOnce(new Error('late failure'))
      .mockResolvedValueOnce(undefined)
    const onError = vi.fn()
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation, { onError })

    coordinator.begin()
    expect(coordinator.requestStop()).toBe(true)
    coordinator.observeRun('run-late')
    await Promise.resolve()
    await Promise.resolve()

    expect(requestCancellation).toHaveBeenNthCalledWith(1, 'run-late')
    expect(onError).toHaveBeenCalledTimes(1)
    expect(coordinator.requestStop()).toBe(true)
    await Promise.resolve()
    await Promise.resolve()
    expect(requestCancellation).toHaveBeenNthCalledWith(2, 'run-late')
  })

  it('does not let an old failed request reset Stop state for a later stream generation', async () => {
    let rejectOld!: (error: Error) => void
    const requestCancellation = vi.fn()
      .mockImplementationOnce(() => new Promise<void>((_resolve, reject) => { rejectOld = reject }))
      .mockResolvedValueOnce(undefined)
    const coordinator = createAgentStreamCancellationCoordinator(requestCancellation)

    coordinator.begin('old-run')
    expect(coordinator.requestStop()).toBe(true)
    coordinator.finish()
    coordinator.begin('new-run')
    expect(coordinator.requestStop()).toBe(true)

    rejectOld(new Error('old request failed'))
    await Promise.resolve()
    await Promise.resolve()

    expect(coordinator.requestStop()).toBe(false)
    expect(requestCancellation).toHaveBeenCalledTimes(2)
  })
})