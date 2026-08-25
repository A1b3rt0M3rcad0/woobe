import { useEffect, useState } from 'react'
import type { RuntimeEnvironment } from '@/features/agents/types'

let currentSessionId: string | null = null
const listeners = new Set<() => void>()

function storageKey(projectId: string, agentId: string, environment: RuntimeEnvironment) {
  return `woobe:agent-session:${projectId}:${agentId}:${environment}`
}

export function setPlaygroundSessionId(sessionId: string | null) {
  currentSessionId = sessionId
  listeners.forEach((listener) => listener())
}

export function getPlaygroundSessionId() {
  return currentSessionId
}

export function getStoredPlaygroundSessionId(
  projectId: string,
  agentId: string,
  environment: RuntimeEnvironment,
): string | null {
  try {
    return window.localStorage.getItem(storageKey(projectId, agentId, environment))
  } catch {
    return null
  }
}

export function setStoredPlaygroundSessionId(
  projectId: string,
  agentId: string,
  environment: RuntimeEnvironment,
  sessionId: string | null,
) {
  try {
    const key = storageKey(projectId, agentId, environment)
    if (sessionId) window.localStorage.setItem(key, sessionId)
    else window.localStorage.removeItem(key)
  } catch {
    // Storage is only an ergonomic pointer. Session/Run truth remains server-side.
  }
}

export function useLivePlaygroundSessionId(fallback: string | null = null) {
  const [sessionId, setSessionId] = useState<string | null>(() => currentSessionId ?? fallback)

  useEffect(() => {
    const listener = () => setSessionId(currentSessionId ?? fallback)
    listeners.add(listener)
    listener()
    return () => {
      listeners.delete(listener)
    }
  }, [fallback])

  return sessionId
}
