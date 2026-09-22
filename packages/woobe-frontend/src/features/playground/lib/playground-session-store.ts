import { useEffect, useState } from 'react'
import type { RuntimeEnvironment } from '@/features/agents/types'

let currentSessionId: string | null = null
const listeners = new Set<() => void>()

function sessionStorageKey(projectId: string, agentId: string, environment: RuntimeEnvironment) {
  return `woobe:agent-session:${projectId}:${agentId}:${environment}`
}

function runStorageKey(projectId: string, agentId: string, environment: RuntimeEnvironment) {
  return `woobe:agent-active-run:${projectId}:${agentId}:${environment}`
}

function externalContextStorageKey(projectId: string, agentId: string, environment: RuntimeEnvironment) {
  return `woobe:agent-external-context:${projectId}:${agentId}:${environment}`
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
    return window.localStorage.getItem(sessionStorageKey(projectId, agentId, environment))
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
    const key = sessionStorageKey(projectId, agentId, environment)
    if (sessionId) window.localStorage.setItem(key, sessionId)
    else window.localStorage.removeItem(key)
  } catch {
    // Storage is only an ergonomic pointer. Session/Run truth remains server-side.
  }
}

export function getStoredPlaygroundRunId(
  projectId: string,
  agentId: string,
  environment: RuntimeEnvironment,
): string | null {
  try {
    return window.localStorage.getItem(runStorageKey(projectId, agentId, environment))
  } catch {
    return null
  }
}

export function setStoredPlaygroundRunId(
  projectId: string,
  agentId: string,
  environment: RuntimeEnvironment,
  runId: string | null,
) {
  try {
    const key = runStorageKey(projectId, agentId, environment)
    if (runId) window.localStorage.setItem(key, runId)
    else window.localStorage.removeItem(key)
  } catch {
    // Reattach still works by Session lookup when local storage is unavailable.
  }
}

export function getStoredPlaygroundExternalContext(
  projectId: string,
  agentId: string,
  environment: RuntimeEnvironment,
): Record<string, unknown> | null {
  try {
    const raw = window.localStorage.getItem(externalContextStorageKey(projectId, agentId, environment))
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}

export function setStoredPlaygroundExternalContext(
  projectId: string,
  agentId: string,
  environment: RuntimeEnvironment,
  values: Record<string, unknown>,
) {
  try {
    window.localStorage.setItem(
      externalContextStorageKey(projectId, agentId, environment),
      JSON.stringify(values),
    )
  } catch {
    // External Context persistence is only a Playground convenience. Run input remains explicit.
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
