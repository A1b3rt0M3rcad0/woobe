import { useEffect, useState } from 'react'

let currentSessionId: string | null = null
const listeners = new Set<() => void>()

export function setPlaygroundSessionId(sessionId: string | null) {
  currentSessionId = sessionId
  listeners.forEach((listener) => listener())
}

export function getPlaygroundSessionId() {
  return currentSessionId
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
