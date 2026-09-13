import { Outlet } from 'react-router-dom'
import { Orbit } from 'lucide-react'
import { Card } from '@woobe/ui'

export function AuthLayout() {
  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background px-[18px] py-8 sm:px-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 [background-image:linear-gradient(rgba(148,163,184,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.025)_1px,transparent_1px)] [background-size:32px_32px]"
      />

      <div className="relative w-full max-w-[404px]">
        <header className="mb-[14px] flex items-center gap-[11px] px-[2px]">
          <div className="flex h-[29px] w-[29px] shrink-0 items-center justify-center rounded-control border border-border bg-surface text-primary-light">
            <Orbit className="h-[17px] w-[17px]" strokeWidth={1.7} />
          </div>
          <div className="min-w-0">
            <p className="font-mono text-[14px] font-bold leading-[17px] tracking-[0.02em] text-slate-50">WOOBE</p>
            <p className="mt-px font-mono text-[10px] uppercase leading-[12px] tracking-[0.12em] text-muted-foreground">control plane</p>
          </div>
        </header>

        <Card className="overflow-hidden rounded-container border-border bg-surface/[0.96] p-0 shadow-none">
          <div className="border-b border-border px-[15px] py-[11px]">
            <div className="flex items-center gap-[7px] font-mono text-[9px] font-bold uppercase leading-[12px] tracking-[0.12em] text-muted-foreground">
              <span className="h-[5px] w-[5px] bg-primary shadow-[0_0_0_3px_rgba(59,130,246,0.12)]" />
              Secure access
              <span className="h-px min-w-0 flex-1 bg-border" />
            </div>
          </div>

          <div className="p-[15px]">
            <Outlet />
          </div>
        </Card>

        <p className="mt-[10px] text-center font-mono text-[8px] leading-[11px] text-muted-foreground">
          API-first control plane for production agentic systems
        </p>
      </div>
    </main>
  )
}
