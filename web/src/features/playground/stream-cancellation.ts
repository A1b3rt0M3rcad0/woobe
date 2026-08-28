export type AgentRunCancellationRequest = (runId: string) => Promise<unknown> | unknown

export interface AgentStreamCancellationCallbacks {
  onDispatch?: (runId: string) => void
  onConfirmed?: (runId: string) => void
  onError?: (runId: string, error: Error) => void
}

export interface AgentStreamCancellationCoordinator {
  begin: (knownRunId?: string | null) => void
  observeRun: (runId: string | null | undefined) => void
  requestStop: () => boolean
  finish: () => void
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error('Run cancellation could not be confirmed')
}

export function createAgentStreamCancellationCoordinator(
  requestCancellation: AgentRunCancellationRequest,
  callbacks: AgentStreamCancellationCallbacks = {},
): AgentStreamCancellationCoordinator {
  let active = false
  let runId: string | null = null
  let stopRequested = false
  let cancellationDispatched = false

  const dispatchCancellation = () => {
    if (!active || !stopRequested || !runId || cancellationDispatched) return
    const targetRunId = runId
    cancellationDispatched = true
    callbacks.onDispatch?.(targetRunId)
    void Promise.resolve(requestCancellation(targetRunId))
      .then(() => callbacks.onConfirmed?.(targetRunId))
      .catch((error) => callbacks.onError?.(targetRunId, toError(error)))
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
      if (!active || stopRequested) return false
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