import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import type { AgentNodeId, ChatTarget, NetworkBinding, NetworkRun } from './networkWorkspaceTypes'
import { currentSignature, makeExecution, type NetworkExecution, type NetworkTurn } from './networkChatExecution'
import { NetworkChatComposer } from './NetworkChatComposer'
import { NetworkChatHeader } from './NetworkChatHeader'
import { NetworkChatHistory } from './NetworkChatHistory'

interface NetworkChatWorkspaceProps {
  networkName: string
  target: ChatTarget
  bindings: Record<AgentNodeId, NetworkBinding>
  sessionSignature: string
  pinned: boolean
  onTarget: (target: ChatTarget) => void
  onNewSession: (signature: string) => void
  onPin: () => void
  onRun: (run: NetworkRun) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
  onOpenTrace: (execution: NetworkExecution) => void
}

export function NetworkChatWorkspace({ networkName, target, bindings, sessionSignature, pinned, onTarget, onNewSession, onPin, onRun, onSelectAgent, onOpenTrace }: NetworkChatWorkspaceProps) {
  const seed = useMemo(() => makeExecution('I need help with an invoice that was charged twice.', target, bindings), [])
  const [text, setText] = useState('')
  const [turns, setTurns] = useState<NetworkTurn[]>([{ id: 'initial-network-turn', user: 'I need help with an invoice that was charged twice.', answer: seed.answer, parsedOutput: seed.parsedOutput, provider: seed.provider, model: seed.model, usage: seed.usage, execution: seed.execution }])
  const [running, setRunning] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const signature = currentSignature(target, bindings)
  const changed = signature !== sessionSignature
  const counts = Object.values(bindings).reduce<Record<NetworkBinding['source'], number>>((result, binding) => ({ ...result, [binding.source]: result[binding.source] + 1 }), { draft: 0, staging: 0, release: 0 })

  useEffect(() => () => { if (timeoutRef.current) clearTimeout(timeoutRef.current) }, [])
  useEffect(() => { const element = scrollRef.current; if (element) element.scrollTop = element.scrollHeight }, [turns, running])

  const stop = () => {
    const wasRunning = running || Boolean(timeoutRef.current)
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = null
    setRunning(false)
    if (wasRunning) toast.info('Network execution stopped')
  }

  const startNew = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = null
    setRunning(false)
    setTurns([])
    setText('')
    onNewSession(signature)
  }

  const send = (suggestion?: string) => {
    const content = (suggestion ?? text).trim()
    if (!content || running) return
    if (changed && !pinned) return toast.warning('Resolve the session composition before sending')
    setText('')
    setRunning(true)
    timeoutRef.current = setTimeout(() => {
      const result = makeExecution(content, target, bindings)
      setTurns((items) => [...items, { id: result.execution.id, user: content, answer: result.answer, parsedOutput: result.parsedOutput, provider: result.provider, model: result.model, usage: result.usage, execution: result.execution }])
      setRunning(false)
      timeoutRef.current = null
      onRun({ id: result.execution.id, title: content, environment: result.execution.environment, status: result.execution.status, duration: `${(result.execution.durationMs / 1000).toFixed(2)}s`, cost: `$${result.execution.costUsd.toFixed(3)}`, path: result.execution.path, traceId: result.execution.traceId })
    }, 520)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <NetworkChatHeader target={target} counts={counts} changed={changed} pinned={pinned} onTarget={onTarget} onNew={startNew} onPin={onPin} />
      <NetworkChatHistory scrollRef={scrollRef} networkName={networkName} turns={turns} running={running} onSuggestion={send} onSelectAgent={onSelectAgent} onOpenTrace={onOpenTrace} />
      <NetworkChatComposer value={text} running={running} onChange={setText} onSend={() => send()} onStop={stop} />
    </div>
  )
}
