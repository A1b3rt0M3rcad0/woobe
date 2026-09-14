import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MutableRefObject } from 'react'
import { createPortal } from 'react-dom'
import { useNodesInitialized, useReactFlow } from '@xyflow/react'
import { Loader2, Maximize2, Minus, Plus, Workflow } from 'lucide-react'


type Props = {
  nodeCount: number
  edgeCount: number
  fitKey: string
  viewportTouchedRef: MutableRefObject<boolean>
}

function CanvasPreparing() {
  const [showMessage, setShowMessage] = useState(false)

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setShowMessage(true), 120)
    return () => window.clearTimeout(timeoutId)
  }, [])

  return (
    <div
      className="absolute inset-0 z-[60] grid place-items-center bg-background"
      role="status"
      aria-live="polite"
      aria-label="Preparing Network Canvas"
    >
      <div className={`flex flex-col items-center text-center transition-opacity duration-150 ${showMessage ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex h-control-lg w-control-lg items-center justify-center rounded-control border border-primary/25 bg-primary/10 text-primary-light">
          <Loader2 className="h-icon-lg w-icon-lg animate-spin" />
        </div>
        <p className="mt-ui-md font-mono text-system-label font-semibold uppercase tracking-ui-eyebrow text-slate-200">Preparing Canvas</p>
        <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Positioning the Network composition.</p>
      </div>
    </div>
  )
}

export function NetworkCanvasChrome({ nodeCount, edgeCount, fitKey, viewportTouchedRef }: Props) {
  const chromeRef = useRef<HTMLDivElement>(null)
  const [shellElement, setShellElement] = useState<HTMLElement | null>(null)
  const [leftInset, setLeftInset] = useState(0)
  const [leftInsetMeasured, setLeftInsetMeasured] = useState(false)
  const [viewportReady, setViewportReady] = useState(nodeCount === 0)
  const initialFitCompleteRef = useRef(nodeCount === 0)
  const previousFitKeyRef = useRef(fitKey)
  const previousInsetRef = useRef(0)
  const nodesInitialized = useNodesInitialized()
  const { fitView, getViewport, setViewport, zoomIn, zoomOut } = useReactFlow()

  const measureLeftInset = useCallback(() => {
    const shell = chromeRef.current?.closest<HTMLElement>('[data-network-canvas-shell]') ?? null
    setShellElement((current) => current === shell ? current : shell)

    const panel = document.querySelector<HTMLElement>('[data-network-operations-panel]')
    if (!shell || !panel) {
      setLeftInset((current) => current === 0 ? current : 0)
      setLeftInsetMeasured(true)
      return
    }

    const shellRect = shell.getBoundingClientRect()
    const panelRect = panel.getBoundingClientRect()
    const overlap = Math.round(Math.max(
      0,
      Math.min(shellRect.right, panelRect.right) - Math.max(shellRect.left, panelRect.left),
    ))
    setLeftInset((current) => current === overlap ? current : overlap)
    setLeftInsetMeasured(true)
  }, [])

  useLayoutEffect(() => {
    measureLeftInset()
    const mutationObserver = new MutationObserver(measureLeftInset)
    mutationObserver.observe(document.body, { childList: true, subtree: true })
    const shell = chromeRef.current?.closest<HTMLElement>('[data-network-canvas-shell]')
    const resizeObserver = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(measureLeftInset)
    if (shell) resizeObserver?.observe(shell)
    window.addEventListener('resize', measureLeftInset)
    return () => {
      mutationObserver.disconnect()
      resizeObserver?.disconnect()
      window.removeEventListener('resize', measureLeftInset)
    }
  }, [measureLeftInset])

  const fitVisibleArea = useCallback(async (duration: number) => {
    if (nodeCount === 0) return
    const shell = chromeRef.current?.closest<HTMLElement>('[data-network-canvas-shell]')
    const insetRatio = leftInset / Math.max(shell?.clientWidth ?? 1, 1)
    const padding = leftInset > 0
      ? Math.min(0.58, 0.32 + insetRatio * 0.45)
      : 0.32
    await fitView({
      padding,
      maxZoom: leftInset > 0 ? 0.8 : 0.84,
      duration,
    })
    if (leftInset > 0) {
      const viewport = getViewport()
      await setViewport(
        { ...viewport, x: viewport.x + leftInset / 2 },
        { duration },
      )
    }
  }, [fitView, getViewport, leftInset, nodeCount, setViewport])

  useEffect(() => {
    if (initialFitCompleteRef.current || !leftInsetMeasured) return
    if (nodeCount === 0) {
      initialFitCompleteRef.current = true
      setViewportReady(true)
      return
    }
    if (!nodesInitialized) return

    let cancelled = false
    const frame = requestAnimationFrame(() => {
      void (async () => {
        try {
          await fitVisibleArea(0)
        } finally {
          if (cancelled) return
          initialFitCompleteRef.current = true
          previousFitKeyRef.current = fitKey
          previousInsetRef.current = leftInset
          setViewportReady(true)
        }
      })()
    })

    return () => {
      cancelled = true
      cancelAnimationFrame(frame)
    }
  }, [fitKey, fitVisibleArea, leftInset, leftInsetMeasured, nodeCount, nodesInitialized])

  useEffect(() => {
    if (!initialFitCompleteRef.current) {
      previousFitKeyRef.current = fitKey
      return
    }
    if (previousFitKeyRef.current === fitKey) return
    previousFitKeyRef.current = fitKey
    if (viewportTouchedRef.current) return

    const frame = requestAnimationFrame(() => { void fitVisibleArea(180) })
    return () => cancelAnimationFrame(frame)
  }, [fitKey, fitVisibleArea, viewportTouchedRef])

  useEffect(() => {
    const previousInset = previousInsetRef.current
    previousInsetRef.current = leftInset
    if (!initialFitCompleteRef.current || previousInset === leftInset || viewportTouchedRef.current) return

    const frame = requestAnimationFrame(() => { void fitVisibleArea(180) })
    return () => cancelAnimationFrame(frame)
  }, [fitVisibleArea, leftInset, viewportTouchedRef])

  const preparingSurface = viewportReady ? null : <CanvasPreparing />

  return (
    <>
      {!viewportReady && !shellElement ? preparingSurface : null}
      {!viewportReady && shellElement ? createPortal(preparingSurface, shellElement) : null}

      <div
        ref={chromeRef}
        className="absolute bottom-ui-md z-20 flex flex-col overflow-hidden rounded-control border border-border bg-background transition-[left] duration-200"
        style={{ left: leftInset + 16 }}
      >
        <button
          type="button"
          title="Zoom in"
          aria-label="Zoom in"
          onClick={() => {
            viewportTouchedRef.current = true
            void zoomIn()
          }}
          className="flex h-control-sm w-control-sm items-center justify-center border-b border-border bg-control/55 text-muted-foreground transition-colors hover:bg-accent hover:text-white"
        >
          <Plus className="h-icon w-icon" />
        </button>
        <button
          type="button"
          title="Zoom out"
          aria-label="Zoom out"
          onClick={() => {
            viewportTouchedRef.current = true
            void zoomOut()
          }}
          className="flex h-control-sm w-control-sm items-center justify-center border-b border-border bg-control/55 text-muted-foreground transition-colors hover:bg-accent hover:text-white"
        >
          <Minus className="h-icon w-icon" />
        </button>
        <button
          type="button"
          title="Fit Network in the visible Canvas"
          aria-label="Fit Network in the visible Canvas"
          onClick={() => {
            viewportTouchedRef.current = false
            void fitVisibleArea(180)
          }}
          className="flex h-control-sm w-control-sm items-center justify-center bg-control/55 text-muted-foreground transition-colors hover:bg-accent hover:text-white"
        >
          <Maximize2 className="h-icon w-icon" />
        </button>
      </div>

      <div
        className="pointer-events-none absolute top-ui-md z-10 flex items-center gap-ui-sm rounded-control border border-border bg-surface/90 px-ui-md py-ui-sm font-mono text-system-micro text-muted-foreground transition-[left] duration-200"
        style={{ left: leftInset + 16 }}
      >
        <Workflow className="h-3.5 w-3.5 text-primary-light" />
        <span><b className="text-white">{nodeCount}</b> Agents · <b className="text-white">{edgeCount}</b> delegations</span>
      </div>
    </>
  )
}
