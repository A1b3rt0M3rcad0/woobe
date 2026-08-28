import { Outlet } from 'react-router-dom'

const controlPlaneAreas = [
  'AGENTS',
  'NETWORKS',
  'RUNS',
  'RELEASES',
  'OBSERVABILITY',
  'KNOWLEDGE',
]

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-background text-white">
      <div className="h-px w-full bg-border" />

      <main className="mx-auto grid min-h-[calc(100vh-1px)] w-full max-w-6xl items-center gap-12 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_420px] lg:px-10">
        <section className="hidden min-w-0 lg:flex lg:min-h-[560px] lg:flex-col lg:justify-between lg:py-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-primary-light">
            Woobe / Control Plane
          </p>

          <div className="max-w-xl">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] text-muted">
              Production operations
            </p>
            <h1 className="mt-3 max-w-lg text-[32px] font-semibold leading-[1.12] tracking-tight text-white">
              Control plane for AI products.
            </h1>
            <p className="mt-4 max-w-lg text-[13px] leading-6 text-muted">
              Operate Agents, Networks, Runs and Releases from one controlled surface.
            </p>

            <div className="mt-8 border-y border-border/80 py-4">
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                {controlPlaneAreas.map((area) => (
                  <div
                    key={area}
                    className="flex items-center gap-2 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-400"
                  >
                    <span className="h-px w-3 shrink-0 bg-border" />
                    {area}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            Controlled / Versioned / Observable
          </p>
        </section>

        <section className="w-full min-w-0">
          <div className="mx-auto w-full max-w-[420px]">
            <div className="mb-6 flex items-center justify-between border-b border-border/80 pb-4 lg:hidden">
              <div>
                <p className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-primary-light">
                  Woobe
                </p>
                <p className="mt-1 text-xs text-muted">Control plane access</p>
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">Auth</span>
            </div>

            <div className="rounded-xl border border-border bg-surface/90 p-5 sm:p-6">
              <Outlet />
            </div>

            <p className="mt-4 text-center font-mono text-[10px] leading-4 text-muted">
              Secure access to Woobe.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
