import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@woobe/ui'

import type { RuntimeEnvironment } from '@/features/agents/types'
import { useNetworkRuntimeEnvironments, useUpdateNetworkRuntimeEnvironment } from '@/features/network/hooks'
import { cn } from '@/lib/utils'

const environments: RuntimeEnvironment[] = ['draft', 'staging', 'production']
const menuWidth = 310
const estimatedMenuHeight = 250
const viewportMargin = 12

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function NetworkRuntimeControlsPopover({ networkId, projectId }: { networkId: string; projectId: string }) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const [open, setOpen] = useState(false)
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0, width: menuWidth })
  const statesQuery = useNetworkRuntimeEnvironments(networkId, projectId)
  const updateRuntime = useUpdateNetworkRuntimeEnvironment(networkId, projectId)

  const enabledCount = environments.filter((environment) => statesQuery.data?.[environment]?.enabled ?? true).length

  function openMenu() {
    const button = buttonRef.current
    if (!button) return
    const rect = button.getBoundingClientRect()
    const width = Math.min(menuWidth, window.innerWidth - viewportMargin * 2)
    const left = Math.min(Math.max(viewportMargin, rect.right - width), window.innerWidth - width - viewportMargin)
    const top = rect.bottom + 8 + estimatedMenuHeight <= window.innerHeight
      ? rect.bottom + 8
      : Math.max(viewportMargin, rect.top - estimatedMenuHeight - 8)
    setMenuPosition({ top, left, width })
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return
    function handlePointerDown(event: PointerEvent) {
      const target = event.target
      if (!(target instanceof Node)) return
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    function handleKeyDown(event: KeyboardEvent) { if (event.key === 'Escape') setOpen(false) }
    function closeForViewportChange() { setOpen(false) }
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    window.addEventListener('resize', closeForViewportChange)
    window.addEventListener('scroll', closeForViewportChange, true)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('resize', closeForViewportChange)
      window.removeEventListener('scroll', closeForViewportChange, true)
    }
  }, [open])

  async function updateEnabled(environment: RuntimeEnvironment, enabled: boolean) {
    if (updateRuntime.isPending) return
    try {
      await updateRuntime.mutateAsync({ environment, enabled })
      toast.success(`${titleCase(environment)} Network runtime ${enabled ? 'enabled' : 'disabled'}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Network runtime')
    }
  }

  const menu = open ? (
    <div ref={menuRef} className="fixed z-focus overflow-hidden rounded-container border border-border bg-surface/95 shadow-popup backdrop-blur-md" style={menuPosition}>
      <div className="flex items-center justify-between border-b border-border px-ui-md py-ui-sm">
        <div>
          <p className="font-mono text-system-control font-semibold text-accent-foreground">Network runtime</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Control Network Runs by environment.</p>
        </div>
        <Button type="button" variant="ghost" size="iconXs" onClick={() => setOpen(false)} aria-label="Close runtime controls"><X className="h-icon-sm w-icon-sm" /></Button>
      </div>

      <div className="divide-y divide-border/70">
        {environments.map((environment) => {
          const enabled = statesQuery.data?.[environment]?.enabled ?? true
          return (
            <div key={environment} className="flex items-center justify-between gap-ui-md px-ui-md py-ui-sm">
              <div className="flex min-w-0 items-center gap-ui-sm">
                <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', enabled ? 'bg-success' : 'bg-muted')} />
                <div className="min-w-0">
                  <p className="font-mono text-system-control font-medium text-accent-foreground">{titleCase(environment)}</p>
                  <p className="font-sans text-product-caption text-muted-foreground">{enabled ? 'Runs allowed' : 'Runs blocked'}</p>
                </div>
              </div>

              <button
                type="button"
                aria-pressed={enabled}
                disabled={updateRuntime.isPending || statesQuery.isLoading}
                onClick={() => void updateEnabled(environment, !enabled)}
                className={cn(
                  'relative h-5 w-9 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                  enabled ? 'border-success/40 bg-success/20' : 'border-border bg-control',
                )}
                title={enabled ? `Disable ${environment} runtime` : `Enable ${environment} runtime`}
              >
                <span className={cn('absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-accent-foreground transition-transform', enabled ? 'translate-x-4' : 'translate-x-0')} />
              </button>
            </div>
          )
        })}
      </div>

      <p className="border-t border-border px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">Existing Runs continue. Canvas, traces and releases remain available.</p>
    </div>
  ) : null

  return (
    <div ref={rootRef} className="relative z-playground-chrome flex items-center">
      <Button
        ref={buttonRef}
        type="button"
        size="sm"
        variant={open ? 'secondary' : 'outline'}
        aria-expanded={open}
        onClick={() => open ? setOpen(false) : openMenu()}
        title="Network runtime environments"
      >
        <span className={cn('mr-ui-xs h-1.5 w-1.5 rounded-full', enabledCount === environments.length ? 'bg-success' : enabledCount === 0 ? 'bg-muted' : 'bg-warning')} />
        <span>Runtime</span>
        <span className="ml-ui-xs text-muted-foreground">{enabledCount}/{environments.length}</span>
        <ChevronDown className={cn('ml-ui-xs h-icon-sm w-icon-sm text-muted-foreground transition-transform', open && 'rotate-180')} />
      </Button>
      {typeof document !== 'undefined' && menu ? createPortal(menu, document.body) : null}
    </div>
  )
}
