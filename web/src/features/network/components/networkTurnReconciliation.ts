import type { NetworkTurn } from './networkChatExecution'

export function reconcileNetworkTurns(
  persistedTurns: NetworkTurn[],
  localTurns: NetworkTurn[],
): NetworkTurn[] {
  const persistedIds = new Set(persistedTurns.map((turn) => turn.id))
  return [
    ...persistedTurns,
    ...localTurns.filter((turn) => !persistedIds.has(turn.id)),
  ]
}
