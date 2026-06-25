import { createContext, useContext, type ReactNode } from 'react'

type PlaygroundRuntimeContextValue = {
  projectId: string
  agentId: string
  sessionId: string | null
}

const PlaygroundRuntimeContext = createContext<PlaygroundRuntimeContextValue | null>(null)

export function PlaygroundRuntimeProvider({
  value,
  children,
}: {
  value: PlaygroundRuntimeContextValue
  children: ReactNode
}) {
  return (
    <PlaygroundRuntimeContext.Provider value={value}>
      {children}
    </PlaygroundRuntimeContext.Provider>
  )
}

export function usePlaygroundRuntime() {
  const context = useContext(PlaygroundRuntimeContext)
  if (!context) {
    return { projectId: '', agentId: '', sessionId: null }
  }
  return context
}
