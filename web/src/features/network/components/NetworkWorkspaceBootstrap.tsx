import { Loader2 } from 'lucide-react'

export function NetworkWorkspaceBootstrap({ networkName }: { networkName: string }) {
  return (
    <div
      className="fixed inset-0 z-[500] flex min-h-svh min-w-0 flex-col overflow-hidden bg-background"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="Preparing Network workspace"
    >
      <header className="flex h-14 shrink-0 items-center border-b border-border bg-surface/80 px-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{networkName}</p>
          <p className="mt-0.5 text-[10px] text-muted">Preparing the Project Network</p>
        </div>
        <span className="ml-auto rounded-md border border-border bg-background/50 px-2 py-1 text-[9px] font-semibold uppercase tracking-wide text-muted">
          Loading
        </span>
      </header>

      <main className="relative grid min-h-0 flex-1 place-items-center overflow-hidden px-6 pb-[8vh] pt-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(59,130,246,0.09),transparent_36%)]" />
        <section className="relative w-full max-w-2xl rounded-3xl border border-border/90 bg-surface/95 px-8 py-10 shadow-2xl shadow-black/30 sm:px-10">
          <div className="flex flex-col items-center text-center">
            <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 text-primary-light">
              <div className="absolute inset-0 rounded-2xl bg-primary/10 blur-lg" />
              <Loader2 className="relative h-6 w-6 animate-spin" />
            </div>
            <p className="mt-5 text-[9px] font-semibold uppercase tracking-[0.2em] text-primary-light">Network workspace</p>
            <h1 className="mt-2 text-xl font-semibold tracking-tight text-white">Preparing Network</h1>
            <p className="mt-3 max-w-md text-[11px] leading-5 text-muted">
              Loading the Draft composition and Project Agent inventory before showing the next valid action.
            </p>
          </div>

          <div className="mt-8 space-y-3" aria-hidden="true">
            <div className="h-11 animate-pulse rounded-xl border border-border/70 bg-background/45" />
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="h-16 animate-pulse rounded-xl border border-border/70 bg-background/35" />
              <div className="h-16 animate-pulse rounded-xl border border-border/70 bg-background/35" />
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
