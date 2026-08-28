import { useSyncExternalStore } from 'react'

export type AgentStreamStopState = 'idle' | 'running' | 'stopping'

let currentState: AgentStreamStopState = 'idle'
const listeners = new Set<() => void>()

export function getAgentStreamStopState(): AgentStreamStopState {
  return currentState
}

export function subscribeAgentStreamStopState(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setAgentStreamStopState(nextState: AgentStreamStopState): void {
  if (nextState === currentState) return
  currentState = nextState
  for (const listener of listeners) listener()
}

export function resetAgentStreamStopState(): void {
  setAgentStreamStopState('idle')
}

export function useAgentStreamStopState(): AgentStreamStopState {
  return useSyncExternalStore(
    subscribeAgentStreamStopState,
    getAgentStreamStopState,
    getAgentStreamStopState,
  )
}
