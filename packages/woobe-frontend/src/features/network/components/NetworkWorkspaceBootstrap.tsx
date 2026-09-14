import { Loader2 } from 'lucide-react'
import { SectionBlock, Skeleton } from '@woobe/ui'

export function NetworkWorkspaceBootstrap({ networkName }: { networkName: string }) {
  return (
    <div
      className="fixed inset-0 z-[500] flex min-h-svh min-w-0 flex-col overflow-hidden bg-background"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="Preparing Network workspace"
    >
      <header className="flex h-[54px] shrink-0 items-center border-b border-border bg-surface/80 px-4">
        <div className="min-w-0">
          <p className="truncate font-mono text-[11px] font-semibold text-slate-100">{networkName}</p>
          <p className="mt-0.5 font-sans text-[10px] text-muted">Preparing the Project Network</p>
        </div>
        <span className="ml-auto rounded-technical border border-border bg-control px-2 py-1 font-mono text-[8px] font-semibold uppercase tracking-[0.12em] text-muted">
          Loading
        </span>
      </header>

      <main className="grid min-h-0 flex-1 place-items-center overflow-hidden px-4 py-6">
        <SectionBlock
          className="w-full max-w-xl bg-surface/65"
          eyebrow="Network workspace"
          title="Preparing Network"
          description="Loading the Draft composition and Project Agent inventory before showing the next valid action."
          actions={<Loader2 className="h-4 w-4 animate-spin text-primary-light" />}
        >
          <div className="grid gap-2 sm:grid-cols-2" aria-hidden="true">
            <Skeleton className="h-10 sm:col-span-2" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        </SectionBlock>
      </main>
    </div>
  )
}
