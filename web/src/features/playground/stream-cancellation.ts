export type AgentRunCancellationRequest = (runId: string) => Promise<unknown> | unknown

export interface AgentStreamCancellationCoordinator {
  begin: (knownRunId?: string | null) => void
  observeRun: (runId: string | null | undefined) => void
  requestStop: () => boolean
  finish: () => void
}

export function createAgentStreamCancellationCoordinator(
  requestCancellation: AgentRunCancellationRequest,
): AgentStreamCancellationCoordinator {
  let active = false
  let runId: string | null = null
  let stopRequested = false
  let cancellationDispatched = false

  const dispatchCancellation = () => {
    if (!active || !stopRequested || !runId || cancellationDispatched) return
    cancellationDispatched = true
    void Promise.resolve(requestCancellation(runId)).catch(() => undefined)
  }

  return {
    begin(knownRunId = null) {
      active = true
      runId = knownRunId
      stopRequested = false
      cancellationDispatched = false
    },

    observeRun(nextRunId) {
      if (!active || !nextRunId) return
      runId = nextRunId
      dispatchCancellation()
    },

    requestStop() {
      if (!active) return false
      stopRequested = true
      dispatchCancellation()
      return true
    },

    finish() {
      active = false
      runId = null
      stopRequested = false
      cancellationDispatched = false
    },
  }
}
