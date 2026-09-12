import { Outlet } from 'react-router-dom'
import { Activity, Boxes, GitBranch, Orbit, ShieldCheck } from 'lucide-react'
import { Badge, Card } from '@woobe/ui'

const operationalSignals = [
  { label: 'Release lifecycle', value: 'Draft → Staging → Production', icon: GitBranch },
  { label: 'Runtime evidence', value: 'Runs · Traces · Cost', icon: Activity },
  { label: 'Controlled assets', value: 'Models · Tools · Knowledge', icon: Boxes },
]

const controlPlaneTopology = String.raw`models ──────────┐
tools ───────────┼── [ WOOBE ] ─── runtime
knowledge ───────┘       │
                         ├── runs
                         └── traces · cost`

export function AuthLayout() {
  return (
    <div className="relative min-h-svh overflow-hidden bg-background text-accent-foreground">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-35 [background-image:linear-gradient(rgba(148,163,184,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.045)_1px,transparent_1px)] [background-size:32px_32px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent"
      />

      <main className="relative mx-auto grid min-h-svh w-full max-w-[1440px] lg:grid-cols-[minmax(0,1fr)_480px]">
        <section className="hidden min-w-0 border-r border-border/90 px-12 py-10 lg:flex lg:flex-col xl:px-16">
          <header className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-control border border-border bg-surface text-primary-light">
                <Orbit className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight text-slate-50">Woobe</p>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">control plane</p>
              </div>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">production systems</span>
          </header>

          <div className="flex flex-1 items-center py-12">
            <div className="w-full max-w-2xl">
              <Badge variant="outline" className="font-mono uppercase tracking-[0.12em]">
                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                API-first operations
              </Badge>

              <h1 className="mt-6 max-w-xl text-[2.55rem] font-semibold leading-[1.08] tracking-[-0.035em] text-slate-50">
                Operate agentic systems with release-grade control.
              </h1>
              <p className="mt-4 max-w-xl text-sm leading-6 text-muted-foreground">
                One control surface for configuration, releases, execution, traces, cost and runtime operations.
              </p>

              <Card className="mt-8 overflow-hidden bg-surface/[0.55] shadow-none">
                <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">control topology</span>
                  <span className="font-mono text-[10px] text-muted">woobe://control-plane</span>
                </div>
                <pre className="overflow-x-auto px-5 py-6 font-mono text-[12px] leading-6 text-slate-400" aria-hidden="true">
                  {controlPlaneTopology}
                </pre>
                <div className="grid border-t border-border sm:grid-cols-3 sm:divide-x sm:divide-border">
                  {operationalSignals.map((item) => {
                    const Icon = item.icon
                    return (
                      <div key={item.label} className="border-b border-border px-4 py-3 last:border-b-0 sm:border-b-0">
                        <div className="flex items-center gap-2 text-slate-200">
                          <Icon className="h-3.5 w-3.5 text-primary-light" />
                          <span className="text-xs font-medium">{item.label}</span>
                        </div>
                        <p className="mt-1.5 font-mono text-[10px] leading-4 text-muted-foreground">{item.value}</p>
                      </div>
                    )
                  })}
                </div>
              </Card>
            </div>
          </div>

          <footer className="flex items-center justify-between border-t border-border/80 pt-4 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
            <span>release · runtime · trace · control</span>
            <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground" />
          </footer>
        </section>

        <section className="flex min-h-svh items-center justify-center px-5 py-8 sm:px-8 lg:px-10">
          <div className="w-full max-w-[408px]">
            <div className="mb-6 flex items-center gap-3 lg:hidden">
              <div className="flex h-9 w-9 items-center justify-center rounded-control border border-border bg-surface text-primary-light">
                <Orbit className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-50">Woobe</p>
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">control plane access</p>
              </div>
            </div>

            <div className="mb-3 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
              <span>workspace access</span>
              <span>secure session</span>
            </div>

            <Card className="border-border/95 bg-surface/[0.88] p-5 shadow-xl shadow-black/20 sm:p-6">
              <Outlet />
            </Card>

            <p className="mt-4 text-center font-mono text-[10px] leading-5 text-muted">
              Access is scoped to authenticated workspace operations.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
