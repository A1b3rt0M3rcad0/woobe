import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageSquare, RefreshCw } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Dialog,
  EmptyStatePanel,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'

import { createChatSurfaceTestSession } from '@/features/chat-surfaces/api'
import type { ChatSurface, ChatSurfaceTestSession } from '@/features/chat-surfaces/types'
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

function statusVariant(status: FrameStatus) {
  if (status === 'error' || status === 'expired') return 'destructive' as const
  if (status === 'running') return 'warning' as const
  if (status === 'ready') return 'success' as const
  return 'outline' as const
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
      setError(requestError instanceof Error ? requestError.message : 'Unable to create a ChatSurface test Session')
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
      ) return

      if (event.data.type === 'ready') {
        frameRef.current?.contentWindow?.postMessage({
          protocolVersion: 1,
          instanceId,
          surfaceId: surface.public_id,
          type: 'init',
          payload: {
            token: session.session_token,
            hostOrigin: window.location.origin,
            apiBaseUrl: API_BASE_URL,
          },
        }, embedOrigin)
        return
      }

      if (event.data.type === 'history.loaded' || event.data.type === 'run.completed') setFrameStatus('ready')
      else if (event.data.type === 'run.started') setFrameStatus('running')
      else if (event.data.type === 'session.expired') setFrameStatus('expired')
      else if (event.data.type === 'error') setFrameStatus('error')
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [embedOrigin, instanceId, open, session, surface.public_id])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Test ChatSurface"
      className="flex h-[min(820px,calc(100svh-2rem))] w-[min(96rem,calc(100vw-2rem))] max-w-none flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="flex h-full min-h-0 flex-col lg:flex-row">
        <div className="min-h-0 min-w-0 flex-1 bg-background/55 p-ui-md">
          <div className="h-full min-h-80 overflow-hidden rounded-container border border-border bg-background">
            {loading ? (
              <EmptyStatePanel
                compact
                icon={<MessageSquare className="h-icon-lg w-icon-lg" />}
                title="Creating test Session"
                description="Preparing a real Control Plane test Session against the pinned Release."
                className="h-full border-0 bg-transparent"
              />
            ) : error ? (
              <div className="flex h-full items-center justify-center p-ui-lg">
                <Alert variant="destructive" className="w-full max-w-dialog-compact">
                  <AlertTitle>Unable to start live test</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                  <Button type="button" size="sm" variant="outline" className="mt-ui-md" onClick={() => void startSession()}>
                    Try again
                  </Button>
                </Alert>
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

        <aside className="flex min-h-0 w-full shrink-0 flex-col border-t border-border bg-surface/90 lg:w-[22rem] lg:border-l lg:border-t-0">
          <div className="shrink-0 border-b border-border p-ui-md">
            <TechnicalListItem
              label="Runtime status"
              description="Live test"
              meta={<Badge variant={statusVariant(frameStatus)} size="compact">{statusLabel(frameStatus)}</Badge>}
            />
          </div>

          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-md">
            <div className="grid gap-ui-md">
              <SectionBlock title="Session metadata" density="compact">
                <div className="grid gap-ui-xs">
                  <TechnicalListItem label="Surface" description={surface.name} />
                  <TechnicalListItem label="Target" description={targetName} />
                  <TechnicalListItem
                    label="Release"
                    description={shortId(session?.target_release_id ?? surface.target_release_id)}
                    title={session?.target_release_id ?? surface.target_release_id}
                  />
                  <TechnicalListItem
                    label="Session"
                    description={session ? shortId(session.session_id) : 'Creating…'}
                    title={session?.session_id}
                  />
                </div>
              </SectionBlock>

              <SectionBlock title="Production behavior" density="compact">
                <p className="font-sans text-product-small leading-5 text-muted-foreground">
                  This creates a real Session against the Release pinned by this ChatSurface. The Session is marked as a Control Plane test and does not require an integrator Access Key.
                </p>
              </SectionBlock>
            </div>
          </div>

          <div className="shrink-0 border-t border-border p-ui-md">
            <Button
              type="button"
              variant="outline"
              className="w-full justify-center"
              disabled={loading || surface.status !== 'active'}
              onClick={() => void startSession()}
            >
              <RefreshCw className="h-icon w-icon" />
              New session
            </Button>
          </div>
        </aside>
      </div>
    </Dialog>
  )
}
