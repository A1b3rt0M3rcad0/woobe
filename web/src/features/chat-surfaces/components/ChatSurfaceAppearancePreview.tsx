import { useEffect, useMemo, useRef } from 'react'

import type { ChatSurfaceAppearance } from '@/features/chat-surfaces/types'

function resolveEmbedOrigin(): string {
  const configured = import.meta.env.VITE_CHAT_EMBED_URL?.trim() || 'http://localhost:8081'
  const url = new URL(configured)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('VITE_CHAT_EMBED_URL must use HTTP(S)')
  }
  return url.origin
}

export function ChatSurfaceAppearancePreview({
  appearance,
}: {
  appearance: ChatSurfaceAppearance
}) {
  const frameRef = useRef<HTMLIFrameElement | null>(null)
  const embedOrigin = useMemo(() => resolveEmbedOrigin(), [])
  const previewUrl = useMemo(
    () => new URL('/chat/v1/preview.html', `${embedOrigin}/`).toString(),
    [embedOrigin],
  )

  const syncAppearance = () => {
    frameRef.current?.contentWindow?.postMessage(
      {
        type: 'woobe.preview.update',
        appearance,
      },
      embedOrigin,
    )
  }

  useEffect(() => {
    syncAppearance()
  }, [appearance, embedOrigin])

  return (
    <section className="self-start rounded-xl border border-border/80 bg-surface/65 p-5">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Preview</p>
      <div className="mt-4 overflow-hidden rounded-xl border border-border/80 bg-background">
        <iframe
          ref={frameRef}
          src={previewUrl}
          title="ChatSurface appearance preview"
          sandbox="allow-scripts allow-same-origin"
          className="pointer-events-none block h-[320px] w-full border-0"
          onLoad={syncAppearance}
        />
      </div>
      <p className="mt-3 text-[11px] leading-5 text-muted">
        Rendered by the same ChatSurface UI package used by the production embed. It does not create a Session or execute the target.
      </p>
    </section>
  )
}
