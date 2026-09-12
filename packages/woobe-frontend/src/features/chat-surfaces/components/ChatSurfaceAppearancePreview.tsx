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
    <section className="min-w-0 self-start overflow-hidden rounded-container border border-border bg-surface/[0.92]">
      <div className="flex h-[46px] min-w-0 items-center justify-between gap-3 border-b border-border px-3.5">
        <div className="min-w-0">
          <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.13em] text-muted-foreground">Preview</p>
          <p className="mt-0.5 truncate font-mono text-[9px] text-slate-300">Production renderer</p>
        </div>
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
            <Maximize2 className="mr-1.5 h-3 w-3" />
            Test live
          </Button>
        ) : null}
      </div>

      <iframe
        ref={frameRef}
        src={previewUrl}
        title="ChatSurface appearance preview"
        sandbox="allow-scripts allow-same-origin"
        className="block h-[340px] w-full min-w-0 border-0 bg-background"
        onLoad={syncAppearance}
      />

      <div className="border-t border-border px-3.5 py-3">
        <p className="font-sans text-[10px] leading-4 text-muted-foreground">
          Same ChatSurface renderer used by the production embed. Preview does not create a Session or execute the target.
        </p>
        {testDisabledReason ? (
          <p className="mt-2 font-mono text-[9px] leading-4 text-amber-200/80">{testDisabledReason}</p>
        ) : null}
      </div>
    </section>
  )
}
