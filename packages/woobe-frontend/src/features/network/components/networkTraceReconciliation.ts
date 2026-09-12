import type { NetworkTraceRecord } from './networkObservabilityTypes'

function isTerminalTrace(trace: NetworkTraceRecord): boolean {
  return trace.status !== 'running'
}

export function persistedTraceSupersedesLocal(
  persisted: NetworkTraceRecord,
  local: NetworkTraceRecord,
): boolean {
  if (persisted.id !== local.id) return false
  if (isTerminalTrace(local) && !isTerminalTrace(persisted)) return false
  return true
}

export function reconcileNetworkTraces(
  persistedTraces: NetworkTraceRecord[],
  currentTraces: NetworkTraceRecord[],
  networkSessionId: string,
): NetworkTraceRecord[] {
  const currentById = new Map(currentTraces.map((trace) => [trace.id, trace]))
  const persistedIds = new Set(persistedTraces.map((trace) => trace.id))

  return [
    ...persistedTraces.map((persisted) => {
      const local = currentById.get(persisted.id)
      return local && !persistedTraceSupersedesLocal(persisted, local)
        ? local
        : persisted
    }),
    ...currentTraces.filter((trace) => (
      trace.networkSessionId !== networkSessionId || !persistedIds.has(trace.id)
    )),
  ]
}
