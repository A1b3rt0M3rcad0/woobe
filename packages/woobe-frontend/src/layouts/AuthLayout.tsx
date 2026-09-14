import { Outlet } from 'react-router-dom'
import { Orbit } from 'lucide-react'
import { Card } from '@woobe/ui'

export function AuthLayout() {
  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background bg-technical-grid px-ui-content-gutter py-ui-xxl sm:px-ui-xxl">
      <div className="relative w-full max-w-form-narrow">
        <header className="mb-ui-stack flex items-center gap-ui-md px-ui-hairline">
          <div className="flex h-control-sm w-control-sm shrink-0 items-center justify-center rounded-control border border-border bg-surface text-primary-light">
            <Orbit className="h-icon-lg w-icon-lg" strokeWidth={1.7} />
          </div>
          <div className="min-w-0">
            <p className="font-mono text-brand-title font-bold text-slate-50">WOOBE</p>
            <p className="mt-ui-hairline font-mono text-brand-caption uppercase text-muted-foreground">control plane</p>
          </div>
        </header>

        <Card className="overflow-hidden rounded-container border-border bg-surface/[0.96] p-0 shadow-none">
          <div className="border-b border-border px-ui-panel-inset py-ui-md">
            <div className="flex items-center gap-ui-sm font-mono text-system-label font-bold uppercase tracking-ui-eyebrow text-muted-foreground">
              <span className="h-ui-xs w-ui-xs bg-primary shadow-[0_0_0_3px_rgba(59,130,246,0.12)]" />
              Secure access
              <span className="h-px min-w-0 flex-1 bg-border" />
            </div>
          </div>

          <div className="p-ui-panel-inset">
            <Outlet />
          </div>
        </Card>

        <p className="mt-ui-md text-center font-mono text-system-micro text-muted-foreground">
          API-first control plane for production agentic systems
        </p>
      </div>
    </main>
  )
}
