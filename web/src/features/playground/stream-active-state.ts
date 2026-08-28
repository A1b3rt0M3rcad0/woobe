import { useSyncExternalStore } from 'react'

let active = false
const listeners = new Set<() => void>()

export function isAgentStreamActive(): boolean {
  return active
}

export function subscribeAgentStreamActiveState(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setAgentStreamActive(nextActive: boolean): void {
  if (nextActive === active) return
  active = nextActive
  for (const listener of listeners) listener()
}

export function resetAgentStreamActiveState(): void {
  setAgentStreamActive(false)
}

export function useAgentStreamActiveState(): boolean {
  return useSyncExternalStore(
    subscribeAgentStreamActiveState,
    isAgentStreamActive,
    isAgentStreamActive,
  )
}
