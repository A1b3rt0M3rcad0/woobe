function storageKey(
  projectId: string,
  agentId: string,
  kind: 'session' | 'run',
) {
  return `woobe:network-agent-chat:${projectId}:${agentId}:${kind}`
}

function readPointer(projectId: string, agentId: string, kind: 'session' | 'run') {
  try {
    return window.localStorage.getItem(storageKey(projectId, agentId, kind))
  } catch {
    return null
  }
}

function writePointer(
  projectId: string,
  agentId: string,
  kind: 'session' | 'run',
  value: string | null,
) {
  try {
    const key = storageKey(projectId, agentId, kind)
    if (value) window.localStorage.setItem(key, value)
    else window.localStorage.removeItem(key)
  } catch {
    // Local storage is only an ergonomic pointer. The active Run remains server-side.
  }
}

export function getStoredNetworkAgentSessionId(projectId: string, agentId: string) {
  return readPointer(projectId, agentId, 'session')
}

export function setStoredNetworkAgentSessionId(
  projectId: string,
  agentId: string,
  sessionId: string | null,
) {
  writePointer(projectId, agentId, 'session', sessionId)
}

export function getStoredNetworkAgentRunId(projectId: string, agentId: string) {
  return readPointer(projectId, agentId, 'run')
}

export function setStoredNetworkAgentRunId(
  projectId: string,
  agentId: string,
  runId: string | null,
) {
  writePointer(projectId, agentId, 'run', runId)
}
