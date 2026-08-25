import { Outlet } from 'react-router-dom'
import { Activity, CheckCircle2, GitBranch, Play, ShieldCheck } from 'lucide-react'

const operationalSignals = [
  { title: 'Release lifecycle', description: 'Draft, staging, production and rollback.', icon: GitBranch },
  { title: 'Runtime observability', description: 'Traces, tool calls, latency, tokens and cost.', icon: Activity },
  { title: 'Operational control', description: 'Models, credentials, tools and contracts in one place.', icon: ShieldCheck },
]

export function AuthLayout() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.14),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(15,23,42,0.88),transparent_42%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />

      <main className="relative mx-auto grid min-h-screen w-full max-w-6xl items-center gap-8 px-5 py-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_440px] lg:px-10">
        <section className="hidden min-w-0 lg:block">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-surface/50 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              Control Plane for Agentic AI Products
            </div>

            <div className="mt-8 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light shadow-[0_0_0_1px_rgba(59,130,246,0.08),0_14px_40px_rgba(37,99,235,0.10)]">
                <Play className="h-5 w-5 fill-current" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">Woobe</p>
                <p className="text-xs text-muted">Control Plane for AI Agents</p>
              </div>
            </div>

            <h1 className="mt-8 max-w-lg text-4xl font-semibold leading-tight tracking-tight text-white">
              Operate AI agents from one production-grade control surface.
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-6 text-muted">
              Access the workspace that controls agents, tools, knowledge, model credentials, releases, traces, usage and runtime environments.
            </p>

            <div className="mt-8 grid max-w-lg gap-3">
              {operationalSignals.map((item) => {
                const Icon = item.icon
                return (
                  <div key={item.title} className="flex items-center gap-3 rounded-xl border border-border/80 bg-surface/45 p-3 shadow-sm">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background/70 text-primary-light">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-100">{item.title}</p>
                      <p className="mt-0.5 text-xs text-muted">{item.description}</p>
                    </div>
                    <CheckCircle2 className="ml-auto h-4 w-4 shrink-0 text-emerald-400" />
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        <section className="w-full min-w-0">
          <div className="mb-5 flex items-center justify-center gap-2 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
              <Play className="h-4 w-4 fill-current" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Woobe</p>
              <p className="text-xs text-muted">Control plane access</p>
            </div>
          </div>

          <div className="rounded-2xl border border-border/90 bg-surface/80 p-5 shadow-2xl shadow-black/25 backdrop-blur sm:p-6">
            <Outlet />
          </div>

          <p className="mt-4 text-center text-[11px] leading-5 text-muted">
            Secure access for workspaces, projects and runtime operations.
          </p>
        </section>
      </main>
    </div>
  )
}
