import { useEffect, useMemo, useRef } from 'react'
import { Maximize2 } from 'lucide-react'

import { Button } from '@/components/ui/Button'
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
  onTest,
  testDisabledReason,
}: {
  appearance: ChatSurfaceAppearance
  onTest?: () => void
  testDisabledReason?: string | null
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
    <section className="min-w-0 self-start overflow-hidden rounded-xl border border-border/80 bg-surface/65 p-4 sm:p-5">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Preview</p>
        {onTest ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0"
            disabled={Boolean(testDisabledReason)}
            title={testDisabledReason ?? 'Open a live test using the pinned Production Release'}
            onClick={onTest}
          >
            <Maximize2 className="mr-2 h-3.5 w-3.5" />
            Test live
          </Button>
        ) : null}
      </div>
      <div className="mt-4 min-w-0 overflow-hidden rounded-xl border border-border/80 bg-background">
        <iframe
          ref={frameRef}
          src={previewUrl}
          title="ChatSurface appearance preview"
          sandbox="allow-scripts allow-same-origin"
          className="block h-[280px] w-full min-w-0 border-0 sm:h-[320px]"
          onLoad={syncAppearance}
        />
      </div>
      <p className="mt-3 break-words text-[11px] leading-5 text-muted">
        Rendered by the same ChatSurface UI package used by the production embed. It does not create a Session or execute the target.
      </p>
      {testDisabledReason ? (
        <p className="mt-2 break-words text-[11px] leading-5 text-amber-200/80">{testDisabledReason}</p>
      ) : null}
    </section>
  )
}
