import { describe, expect, it, vi } from 'vitest'

import { createNetworkLiveAnswerScheduler } from './networkLiveAnswerScheduler'

function frameDriver() {
  let nextId = 1
  const callbacks = new Map<number, FrameRequestCallback>()
  return {
    callbacks,
    driver: {
      request: vi.fn((callback: FrameRequestCallback) => {
        const id = nextId
        nextId += 1
        callbacks.set(id, callback)
        return id
      }),
      cancel: vi.fn((frameId: number) => {
        callbacks.delete(frameId)
      }),
    },
  }
}

describe('createNetworkLiveAnswerScheduler', () => {
  it('coalesces multiple transport updates into one visual frame', () => {
    const commit = vi.fn()
    const { callbacks, driver } = frameDriver()
    const scheduler = createNetworkLiveAnswerScheduler(commit, driver)

    scheduler.schedule('A')
    scheduler.schedule('AB')
    scheduler.schedule('ABC')

    expect(driver.request).toHaveBeenCalledTimes(1)
    expect(commit).not.toHaveBeenCalled()

    callbacks.get(1)?.(0)

    expect(commit).toHaveBeenCalledTimes(1)
    expect(commit).toHaveBeenLastCalledWith('ABC')
  })

  it('schedules another frame after the previous frame was committed', () => {
    const commit = vi.fn()
    const { callbacks, driver } = frameDriver()
    const scheduler = createNetworkLiveAnswerScheduler(commit, driver)

    scheduler.schedule('A')
    callbacks.get(1)?.(0)
    scheduler.schedule('AB')

    expect(driver.request).toHaveBeenCalledTimes(2)
    callbacks.get(2)?.(16)
    expect(commit).toHaveBeenLastCalledWith('AB')
  })

  it('flushes the newest value before a pending frame', () => {
    const commit = vi.fn()
    const { callbacks, driver } = frameDriver()
    const scheduler = createNetworkLiveAnswerScheduler(commit, driver)

    scheduler.schedule('partial')
    scheduler.flush('complete')

    expect(driver.cancel).toHaveBeenCalledWith(1)
    expect(callbacks.has(1)).toBe(false)
    expect(commit).toHaveBeenCalledTimes(1)
    expect(commit).toHaveBeenLastCalledWith('complete')
  })

  it('clears a pending frame without committing stale output', () => {
    const commit = vi.fn()
    const { callbacks, driver } = frameDriver()
    const scheduler = createNetworkLiveAnswerScheduler(commit, driver)

    scheduler.schedule('old run')
    scheduler.clear()

    expect(driver.cancel).toHaveBeenCalledWith(1)
    expect(callbacks.has(1)).toBe(false)
    expect(commit).not.toHaveBeenCalled()
  })

  it('commits immediately when animation frames are unavailable', () => {
    const commit = vi.fn()
    const scheduler = createNetworkLiveAnswerScheduler(commit, null)

    scheduler.schedule('server-safe fallback')

    expect(commit).toHaveBeenCalledWith('server-safe fallback')
  })
})
