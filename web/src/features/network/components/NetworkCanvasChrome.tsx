import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react'
import { useReactFlow } from '@xyflow/react'
import { Maximize2, Minus, Plus, Workflow } from 'lucide-react'

type Props = {
  nodeCount: number
  edgeCount: number
  fitKey: string
  viewportTouchedRef: MutableRefObject<boolean>
}

export function NetworkCanvasChrome({ nodeCount, edgeCount, fitKey, viewportTouchedRef }: Props) {
  const chromeRef = useRef<HTMLDivElement>(null)
  const [leftInset, setLeftInset] = useState(0)
  const { fitView, getViewport, setViewport, zoomIn, zoomOut } = useReactFlow()

  const measureLeftInset = useCallback(() => {
    const shell = chromeRef.current?.closest<HTMLElement>('[data-network-canvas-shell]')
    const panel = document.querySelector<HTMLElement>('[data-network-operations-panel]')
    if (!shell || !panel) {
      setLeftInset(0)
      return
    }
    const shellRect = shell.getBoundingClientRect()
    const panelRect = panel.getBoundingClientRect()
    const overlap = Math.max(
      0,
      Math.min(shellRect.right, panelRect.right) - Math.max(shellRect.left, panelRect.left),
    )
    setLeftInset(Math.round(overlap))
  }, [])

  useEffect(() => {
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
  const fitVisibleAreaRef = useRef(fitVisibleArea)

  useEffect(() => {
    fitVisibleAreaRef.current = fitVisibleArea
  }, [fitVisibleArea])

  useEffect(() => {
    viewportTouchedRef.current = false
    const frame = requestAnimationFrame(() => { void fitVisibleAreaRef.current(0) })
    return () => cancelAnimationFrame(frame)
  }, [fitKey, viewportTouchedRef])

  useEffect(() => {
    if (viewportTouchedRef.current) return
    const frame = requestAnimationFrame(() => { void fitVisibleArea(180) })
    return () => cancelAnimationFrame(frame)
  }, [fitVisibleArea, leftInset, viewportTouchedRef])

  return (
    <>
      <div
        ref={chromeRef}
        className="absolute bottom-4 z-20 flex flex-col overflow-hidden rounded-xl border border-slate-700/90 bg-[#020817] shadow-xl shadow-black/30 transition-[left] duration-200"
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
          className="flex h-8 w-8 items-center justify-center border-b border-slate-700/75 bg-slate-900 text-slate-300 hover:bg-blue-950 hover:text-white"
        >
          <Plus className="h-4 w-4" />
        </button>
        <button
          type="button"
          title="Zoom out"
          aria-label="Zoom out"
          onClick={() => {
            viewportTouchedRef.current = true
            void zoomOut()
          }}
          className="flex h-8 w-8 items-center justify-center border-b border-slate-700/75 bg-slate-900 text-slate-300 hover:bg-blue-950 hover:text-white"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          type="button"
          title="Fit Network in the visible Canvas"
          aria-label="Fit Network in the visible Canvas"
          onClick={() => {
            viewportTouchedRef.current = false
            void fitVisibleArea(180)
          }}
          className="flex h-8 w-8 items-center justify-center bg-slate-900 text-slate-300 hover:bg-blue-950 hover:text-white"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      <div
        className="pointer-events-none absolute top-4 z-10 flex items-center gap-2 rounded-xl border border-border bg-surface/90 px-3 py-2 text-[10px] text-muted shadow-lg transition-[left] duration-200"
        style={{ left: leftInset + 16 }}
      >
        <Workflow className="h-3.5 w-3.5 text-primary-light" />
        <span><b className="text-white">{nodeCount}</b> Agents · <b className="text-white">{edgeCount}</b> delegations</span>
      </div>
    </>
  )
}
