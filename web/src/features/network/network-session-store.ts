import type { Environment } from './components/networkWorkspaceTypes'

function key(projectId: string, networkId: string, environment: Environment) {
  return `woobe:network-session:${projectId}:${networkId}:${environment}`
}

export function getStoredNetworkSessionId(
  projectId: string,
  networkId: string,
  environment: Environment,
): string | null {
  try {
    return window.localStorage.getItem(key(projectId, networkId, environment))
  } catch {
    return null
  }
}

export function setStoredNetworkSessionId(
  projectId: string,
  networkId: string,
  environment: Environment,
  sessionId: string | null,
) {
  try {
    const storageKey = key(projectId, networkId, environment)
    if (sessionId) window.localStorage.setItem(storageKey, sessionId)
    else window.localStorage.removeItem(storageKey)
  } catch {
    // Storage is an ergonomic hint only; backend Session lookup remains canonical.
  }
}
