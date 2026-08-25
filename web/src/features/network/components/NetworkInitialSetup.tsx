import { Bot, CheckCircle2, Plus } from 'lucide-react'

import { cn } from '@/lib/utils'

const secondaryAction = 'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-border bg-background/50 px-4 py-2.5 text-[10px] font-semibold text-slate-200 transition hover:border-primary/35 hover:bg-primary/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

export function NetworkInitialSetup({
  hasAgents,
  pending,
  onChooseAgent,
  onCreateAgent,
}: {
  hasAgents: boolean
  pending: boolean
  onChooseAgent: () => void
  onCreateAgent: () => void
}) {
  return (
    <div
      className="relative grid min-w-0 flex-1 place-items-center overflow-hidden bg-background px-6 pb-[9vh] pt-8"
      aria-label="Network initial setup"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(59,130,246,0.09),transparent_36%)]" />
      <section className="relative w-full max-w-2xl rounded-3xl border border-border/90 bg-surface/95 px-8 py-9 text-center shadow-2xl shadow-black/30 sm:px-10 sm:py-10">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 text-primary-light">
          <Bot className="h-6 w-6" />
        </div>

        <p className="mt-5 text-[9px] font-semibold uppercase tracking-[0.2em] text-primary-light">Network setup</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-white">Choose the entry Agent</h2>
        <p className="mx-auto mt-3 max-w-lg text-[11px] leading-5 text-muted">
          This Agent receives the requests sent to the Network. You can add specialists and delegation paths after validating the first test.
        </p>

        <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
          {hasAgents ? (
            <button
              type="button"
              disabled={pending}
              onClick={onChooseAgent}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-[10px] font-semibold text-white shadow-lg shadow-primary/20 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Bot className="h-3.5 w-3.5" />
              Choose Agent
            </button>
          ) : null}
          <button
            type="button"
            disabled={pending}
            onClick={onCreateAgent}
            className={cn(secondaryAction, !hasAgents && 'border-primary/30 bg-primary text-white shadow-lg shadow-primary/20 hover:bg-primary')}
          >
            <Plus className="h-3.5 w-3.5" />
            {hasAgents ? 'Create new Agent' : 'Create first Agent'}
          </button>
        </div>

        <div className="mt-8 grid gap-3 text-left sm:grid-cols-2">
          <div className="rounded-xl border border-border/80 bg-background/35 px-4 py-3.5">
            <div className="flex items-center gap-2 text-slate-200">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
              <p className="text-[10px] font-medium">Saved automatically</p>
            </div>
            <p className="mt-1.5 text-[9px] leading-4 text-muted">The first node and entry point are persisted together.</p>
          </div>
          <div className="rounded-xl border border-border/80 bg-background/35 px-4 py-3.5">
            <div className="flex items-center gap-2 text-slate-200">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary-light" />
              <p className="text-[10px] font-medium">One Agent is enough</p>
            </div>
            <p className="mt-1.5 text-[9px] leading-4 text-muted">A single entry Agent already creates a valid Network for testing.</p>
          </div>
        </div>

        <div className="mt-7 flex items-center justify-center gap-2 text-[9px] font-medium text-muted" aria-label="Network setup progress">
          <span className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-primary-light">1 · Entry Agent</span>
          <span className="h-px w-8 bg-border" />
          <span className="rounded-full border border-border px-2.5 py-1">2 · First test</span>
        </div>
      </section>
    </div>
  )
}

export function NetworkInitialSetupInspector() {
  return null
}

type NetworkReadyToTestProps = {
  pending: boolean
  onTest: () => void
  onAddSpecialist: () => void
}

export function NetworkReadyToTest(props: NetworkReadyToTestProps) {
  void props
  return null
}
