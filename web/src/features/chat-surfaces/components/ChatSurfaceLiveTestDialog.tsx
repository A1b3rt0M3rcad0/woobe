import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { createChatSurfaceTestSession } from '@/features/chat-surfaces/api'
import type {
  ChatSurface,
  ChatSurfaceTestSession,
} from '@/features/chat-surfaces/types'
import { API_BASE_URL } from '@/lib/api/client'

interface ChatSurfaceLiveTestDialogProps {
  open: boolean
  surface: ChatSurface
  targetName: string
  onClose: () => void
}

type FrameStatus = 'starting' | 'ready' | 'running' | 'expired' | 'error'

function resolveEmbedOrigin(): string {
  const configured = import.meta.env.VITE_CHAT_EMBED_URL?.trim() || 'http://localhost:8081'
  const url = new URL(configured)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('VITE_CHAT_EMBED_URL must use HTTP(S)')
  }
  return url.origin
}

function shortId(value: string): string {
  return value.length > 22 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value
}

function statusLabel(status: FrameStatus): string {
  if (status === 'ready') return 'Ready'
  if (status === 'running') return 'Agent responding'
  if (status === 'expired') return 'Session expired'
  if (status === 'error') return 'Runtime error'
  return 'Starting'
}

export function ChatSurfaceLiveTestDialog({
  open,
  surface,
  targetName,
  onClose,
}: ChatSurfaceLiveTestDialogProps) {
  const frameRef = useRef<HTMLIFrameElement | null>(null)
  const startedSurfaceRef = useRef<string | null>(null)
  const [session, setSession] = useState<ChatSurfaceTestSession | null>(null)
  const [instanceId, setInstanceId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [frameStatus, setFrameStatus] = useState<FrameStatus>('starting')

  const embedOrigin = useMemo(() => resolveEmbedOrigin(), [])
  const frameUrl = useMemo(() => {
    if (!session || !instanceId) return ''
    const url = new URL('/chat/v1/iframe.html', `${embedOrigin}/`)
    url.searchParams.set('surface', surface.public_id)
    url.searchParams.set('instance', instanceId)
    return url.toString()
  }, [embedOrigin, instanceId, session, surface.public_id])

  const startSession = useCallback(async () => {
    setLoading(true)
    setError(null)
    setFrameStatus('starting')
    try {
      const created = await createChatSurfaceTestSession(surface.id)
      setSession(created)
      setInstanceId(crypto.randomUUID())
    } catch (requestError) {
      setSession(null)
      setInstanceId('')
      setFrameStatus('error')
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to create a ChatSurface test Session',
      )
    } finally {
      setLoading(false)
    }
  }, [surface.id])

  useEffect(() => {
    if (!open) {
      startedSurfaceRef.current = null
      setSession(null)
      setInstanceId('')
      setError(null)
      setFrameStatus('starting')
      return
    }
    if (startedSurfaceRef.current === surface.id) return
    startedSurfaceRef.current = surface.id
    void startSession()
  }, [open, startSession, surface.id])

  useEffect(() => {
    if (!open || !session || !instanceId) return

    const onMessage = (event: MessageEvent) => {
      if (
        event.origin !== embedOrigin
        || event.source !== frameRef.current?.contentWindow
        || !event.data
        || event.data.protocolVersion !== 1
        || event.data.instanceId !== instanceId
        || event.data.surfaceId !== surface.public_id
      ) {
        return
      }

      if (event.data.type === 'ready') {
        frameRef.current?.contentWindow?.postMessage(
          {
            protocolVersion: 1,
            instanceId,
            surfaceId: surface.public_id,
            type: 'init',
            payload: {
              token: session.session_token,
              hostOrigin: window.location.origin,
              apiBaseUrl: API_BASE_URL,
            },
          },
          embedOrigin,
        )
        return
      }

      if (event.data.type === 'history.loaded' || event.data.type === 'run.completed') {
        setFrameStatus('ready')
      } else if (event.data.type === 'run.started') {
        setFrameStatus('running')
      } else if (event.data.type === 'session.expired') {
        setFrameStatus('expired')
      } else if (event.data.type === 'error') {
        setFrameStatus('error')
      }
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [embedOrigin, instanceId, open, session, surface.public_id])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Test ChatSurface"
      className="max-h-[calc(100svh-2rem)] max-w-6xl overflow-hidden"
      contentClassName="p-0"
    >
      <div className="grid min-h-[640px] max-h-[calc(100svh-8rem)] lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-h-0 bg-background/45 p-5 lg:p-6">
          <div className="h-full min-h-[560px] overflow-hidden rounded-2xl border border-border bg-background shadow-inner">
            {loading ? (
              <div className="flex h-full min-h-[560px] items-center justify-center text-sm text-muted">
                Creating test Session…
              </div>
            ) : error ? (
              <div className="flex h-full min-h-[560px] items-center justify-center p-8">
                <div className="max-w-md rounded-xl border border-red-500/25 bg-red-500/10 p-5 text-center">
                  <p className="text-sm font-medium text-red-200">Unable to start live test</p>
                  <p className="mt-2 text-xs leading-5 text-red-200/75">{error}</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-4"
                    onClick={() => void startSession()}
                  >
                    Try again
                  </Button>
                </div>
              </div>
            ) : session && frameUrl ? (
              <iframe
                key={`${session.session_id}:${instanceId}`}
                ref={frameRef}
                src={frameUrl}
                title="Live ChatSurface test"
                referrerPolicy="no-referrer"
                sandbox="allow-forms allow-scripts allow-same-origin"
                className="block h-full min-h-[560px] w-full border-0"
              />
            ) : null}
          </div>
        </div>

        <aside className="overflow-y-auto border-t border-border bg-surface/70 p-5 lg:border-l lg:border-t-0">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Live test</p>
              <p className="mt-1 text-sm font-semibold text-white">{statusLabel(frameStatus)}</p>
            </div>
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                frameStatus === 'error' || frameStatus === 'expired'
                  ? 'bg-red-400'
                  : frameStatus === 'running'
                    ? 'bg-amber-300'
                    : frameStatus === 'ready'
                      ? 'bg-emerald-400'
                      : 'bg-slate-500'
              }`}
              aria-hidden="true"
            />
          </div>

          <div className="mt-5 space-y-3 text-xs">
            <div className="rounded-xl border border-border/80 bg-background/55 p-3">
              <p className="uppercase tracking-wider text-muted">Surface</p>
              <p className="mt-1 truncate font-medium text-white" title={surface.name}>{surface.name}</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/55 p-3">
              <p className="uppercase tracking-wider text-muted">Target</p>
              <p className="mt-1 truncate font-medium text-white" title={targetName}>{targetName}</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/55 p-3">
              <p className="uppercase tracking-wider text-muted">Pinned Release</p>
              <p className="mt-1 font-mono text-white" title={session?.target_release_id ?? surface.target_release_id}>
                {shortId(session?.target_release_id ?? surface.target_release_id)}
              </p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/55 p-3">
              <p className="uppercase tracking-wider text-muted">Test Session</p>
              <p className="mt-1 break-all font-mono text-white">
                {session ? shortId(session.session_id) : 'Creating…'}
              </p>
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-primary/20 bg-primary/5 p-4">
            <p className="text-xs font-medium text-white">Production behavior</p>
            <p className="mt-1 text-[11px] leading-5 text-muted">
              This creates a real Session against the Release pinned by this ChatSurface. The Session is marked as a Control Plane test and does not require an integrator Access Key.
            </p>
          </div>

          <Button
            type="button"
            variant="outline"
            className="mt-5 w-full justify-center"
            disabled={loading || surface.status !== 'active'}
            onClick={() => void startSession()}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            New session
          </Button>
        </aside>
      </div>
    </Dialog>
  )
}
