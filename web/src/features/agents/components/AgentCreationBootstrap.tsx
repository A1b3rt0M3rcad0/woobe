import { Loader2, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/Button'

export function AgentCreationPreparing() {
  return (
    <div className="grid min-h-[520px] grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
      <div className="mb-5 grid grid-cols-3 gap-2 rounded-xl border border-border/80 bg-background/55 p-2" aria-hidden="true">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="flex items-center gap-2 rounded-lg px-3 py-2">
            <div className="h-6 w-6 animate-pulse rounded-full border border-border bg-white/[0.05]" />
            <div className="h-2.5 w-20 animate-pulse rounded-full bg-white/[0.06]" />
          </div>
        ))}
      </div>

      <div className="flex min-h-0 flex-col items-center justify-center rounded-xl border border-border/80 bg-surface/65 px-6 py-12 text-center" role="status" aria-live="polite" aria-busy="true">
        <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 text-primary-light">
          <div className="absolute inset-0 rounded-2xl bg-primary/10 blur-lg" />
          <Loader2 className="relative h-5 w-5 animate-spin" />
        </div>
        <p className="mt-5 text-base font-semibold text-white">Preparing Agent setup</p>
        <p className="mt-2 max-w-md text-sm leading-6 text-muted">
          Loading Provider connections and generation models for this Project.
        </p>

        <div className="mt-8 w-full max-w-xl space-y-3" aria-hidden="true">
          <div className="h-10 animate-pulse rounded-lg border border-border/70 bg-background/45" />
          <div className="h-10 animate-pulse rounded-lg border border-border/70 bg-background/45" />
          <div className="h-32 animate-pulse rounded-lg border border-border/70 bg-background/45" />
        </div>
      </div>
    </div>
  )
}

export function AgentCreationLoadError({ onRetry, onCancel }: { onRetry: () => void; onCancel: () => void }) {
  return (
    <div className="flex min-h-[520px] items-center justify-center">
      <section className="w-full max-w-xl rounded-2xl border border-red-500/25 bg-red-500/[0.04] px-6 py-8 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-red-500/30 bg-red-500/10 text-red-300">
          <RefreshCw className="h-5 w-5" />
        </div>
        <h3 className="mt-5 text-base font-semibold text-white">Could not prepare Agent setup</h3>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          The Project Provider connections or generation models could not be loaded. No Agent data was changed.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
          <Button type="button" onClick={onRetry}><RefreshCw className="mr-2 h-4 w-4" />Retry</Button>
        </div>
      </section>
    </div>
  )
}
