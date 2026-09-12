import type { NetworkTurn } from './networkChatExecution'

function isTerminalTurn(turn: NetworkTurn): boolean {
  return turn.execution.status !== 'running'
}

export function persistedTurnSupersedesLocal(
  persisted: NetworkTurn,
  local: NetworkTurn,
): boolean {
  if (persisted.id !== local.id) return false
  if (isTerminalTurn(local) && !isTerminalTurn(persisted)) return false
  return true
}

export function reconcileNetworkTurns(
  persistedTurns: NetworkTurn[],
  localTurns: NetworkTurn[],
): NetworkTurn[] {
  const localById = new Map(localTurns.map((turn) => [turn.id, turn]))
  const persistedIds = new Set(persistedTurns.map((turn) => turn.id))
  return [
    ...persistedTurns.map((persisted) => {
      const local = localById.get(persisted.id)
      return local && !persistedTurnSupersedesLocal(persisted, local)
        ? local
        : persisted
    }),
    ...localTurns.filter((turn) => !persistedIds.has(turn.id)),
  ]
}
