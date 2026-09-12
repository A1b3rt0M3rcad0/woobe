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

function statusClass(status: FrameStatus): string {
  if (status === 'error' || status === 'expired') return 'bg-red-400'
  if (status === 'running') return 'bg-amber-300'
  if (status === 'ready') return 'bg-emerald-400'
  return 'bg-slate-500'
}

function MetadataRow({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-3 py-3">
      <span className="font-mono text-[8px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        {label}
      </span>
      <span className="min-w-0 truncate text-right font-mono text-[10px] font-medium text-slate-100" title={title ?? value}>
        {value}
      </span>
    </div>
  )
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
      className="h-[min(720px,calc(100svh-2rem))] max-w-[1180px] overflow-hidden"
      contentClassName="h-full min-h-0 p-0"
    >
      <div className="grid h-full min-h-0 lg:grid-cols-[minmax(0,1fr)_264px]">
        <div className="min-h-0 bg-background/55 p-3 sm:p-4">
          <div className="h-full min-h-[420px] overflow-hidden rounded-container border border-border bg-background">
            {loading ? (
              <div className="flex h-full items-center justify-center font-mono text-[10px] text-muted-foreground">
                Creating test Session…
              </div>
            ) : error ? (
              <div className="flex h-full items-center justify-center p-6">
                <div className="w-full max-w-md border border-red-500/20 bg-control/75 p-4">
                  <p className="font-mono text-[10px] font-semibold text-red-200">Unable to start live test</p>
                  <p className="mt-2 font-sans text-xs leading-5 text-muted-foreground">{error}</p>
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
                className="block h-full w-full border-0"
              />
            ) : null}
          </div>
        </div>

        <aside className="flex min-h-0 flex-col border-t border-border bg-surface/[0.88] lg:border-l lg:border-t-0">
          <div className="flex h-[58px] shrink-0 items-center justify-between border-b border-border px-4">
            <div className="min-w-0">
              <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.13em] text-muted-foreground">Live test</p>
              <p className="mt-1 truncate font-mono text-[11px] font-semibold text-slate-50">{statusLabel(frameStatus)}</p>
            </div>
            <span className={`h-1.5 w-1.5 shrink-0 ${statusClass(frameStatus)}`} aria-hidden="true" />
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4">
            <div className="divide-y divide-border/70 border-b border-border/70">
              <MetadataRow label="Surface" value={surface.name} />
              <MetadataRow label="Target" value={targetName} />
              <MetadataRow
                label="Release"
                value={shortId(session?.target_release_id ?? surface.target_release_id)}
                title={session?.target_release_id ?? surface.target_release_id}
              />
              <MetadataRow
                label="Session"
                value={session ? shortId(session.session_id) : 'Creating…'}
                title={session?.session_id}
              />
            </div>

            <section className="border-b border-border/70 py-4">
              <p className="font-mono text-[9px] font-semibold text-slate-100">Production behavior</p>
              <p className="mt-1.5 font-sans text-[11px] leading-5 text-muted-foreground">
                This creates a real Session against the Release pinned by this ChatSurface. The Session is marked as a Control Plane test and does not require an integrator Access Key.
              </p>
            </section>
          </div>

          <div className="shrink-0 border-t border-border p-3">
            <Button
              type="button"
              variant="outline"
              className="w-full justify-center"
              disabled={loading || surface.status !== 'active'}
              onClick={() => void startSession()}
            >
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              New session
            </Button>
          </div>
        </aside>
      </div>
    </Dialog>
  )
}
