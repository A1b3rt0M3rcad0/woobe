import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { completeMcpOAuth } from '@/features/tools/api'
import { Button } from '@/components/ui/Button'

const MCP_CONNECT_STATE_PREFIX = 'projectrai:mcp-connect:'

type PendingConnectState = {
  toolId: string
  returnTo: string
}

function readPendingState(state: string): PendingConnectState | null {
  const raw = window.localStorage.getItem(`${MCP_CONNECT_STATE_PREFIX}${state}`)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<PendingConnectState>
    if (!parsed.toolId || !parsed.returnTo) return null
    return { toolId: parsed.toolId, returnTo: parsed.returnTo }
  } catch {
    return null
  }
}

export default function McpConnectCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('Completing MCP connection...')
  const [returnTo, setReturnTo] = useState('/dashboard')

  useEffect(() => {
    let mounted = true

    async function completeConnection() {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const error = searchParams.get('error')

      if (error) {
        setStatus('error')
        setMessage(searchParams.get('error_description') || error)
        return
      }

      if (!code || !state) {
        setStatus('error')
        setMessage('Missing code or state in MCP callback.')
        return
      }

      const pending = readPendingState(state)
      if (!pending) {
        setStatus('error')
        setMessage('MCP connection state was not found or expired locally.')
        return
      }

      setReturnTo(pending.returnTo)

      try {
        await completeMcpOAuth({ tool_id: pending.toolId, code, state })
        window.localStorage.removeItem(`${MCP_CONNECT_STATE_PREFIX}${state}`)
        if (!mounted) return
        setStatus('success')
        setMessage('MCP provider connected.')
        window.setTimeout(() => navigate(pending.returnTo, { replace: true }), 900)
      } catch (err) {
        if (!mounted) return
        setStatus('error')
        setMessage(err instanceof Error ? err.message : 'Failed to complete MCP connection.')
      }
    }

    void completeConnection()
    return () => {
      mounted = false
    }
  }, [navigate, searchParams])

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-xl">
        <p className="mb-2 text-sm uppercase tracking-[0.2em] text-muted">MCP Connect</p>
        <h1 className="text-2xl font-semibold text-white">
          {status === 'loading' ? 'Finishing connection' : status === 'success' ? 'Connected' : 'Connection failed'}
        </h1>
        <p className="mt-3 text-sm text-muted">{message}</p>
        <div className="mt-6 flex justify-end">
          <Button onClick={() => navigate(returnTo)}>{status === 'success' ? 'Back to tools' : 'Return'}</Button>
        </div>
      </div>
    </div>
  )
}
