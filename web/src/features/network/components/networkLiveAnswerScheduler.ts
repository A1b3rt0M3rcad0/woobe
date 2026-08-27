export interface NetworkLiveAnswerScheduler {
  schedule: (value: string) => void
  flush: (value?: string) => void
  clear: () => void
}

interface AnimationFrameDriver {
  request: (callback: FrameRequestCallback) => number
  cancel: (frameId: number) => void
}

function browserAnimationFrameDriver(): AnimationFrameDriver | null {
  if (
    typeof requestAnimationFrame !== 'function'
    || typeof cancelAnimationFrame !== 'function'
  ) return null
  return {
    request: (callback) => requestAnimationFrame(callback),
    cancel: (frameId) => cancelAnimationFrame(frameId),
  }
}

export function createNetworkLiveAnswerScheduler(
  commit: (value: string) => void,
  frameDriver: AnimationFrameDriver | null = browserAnimationFrameDriver(),
): NetworkLiveAnswerScheduler {
  let pendingValue = ''
  let frameId: number | null = null

  const renderPending = () => {
    frameId = null
    commit(pendingValue)
  }

  return {
    schedule(value) {
      pendingValue = value
      if (frameId !== null) return
      if (frameDriver === null) {
        commit(pendingValue)
        return
      }
      frameId = frameDriver.request(renderPending)
    },
    flush(value) {
      if (value !== undefined) pendingValue = value
      if (frameId !== null && frameDriver !== null) {
        frameDriver.cancel(frameId)
      }
      frameId = null
      commit(pendingValue)
    },
    clear() {
      if (frameId !== null && frameDriver !== null) {
        frameDriver.cancel(frameId)
      }
      frameId = null
      pendingValue = ''
    },
  }
}
