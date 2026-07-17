import { Bot, CheckCircle2, MessageSquare, Plus, Workflow } from 'lucide-react'

import { cn } from '@/lib/utils'

const secondaryAction = 'inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-background/50 px-4 py-2.5 text-[10px] font-semibold text-slate-200 transition hover:border-primary/35 hover:bg-primary/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

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
    <div className="relative flex min-w-0 flex-1 items-center justify-center overflow-hidden bg-background p-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.08),transparent_38%)]" />
      <section className="relative w-full max-w-xl rounded-2xl border border-border/90 bg-surface/95 p-8 text-center shadow-2xl shadow-black/30">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 text-primary-light">
          <Workflow className="h-6 w-6" />
        </div>
        <p className="mt-5 text-[9px] font-semibold uppercase tracking-[0.2em] text-primary-light">Initial setup</p>
        <h2 className="mt-2 text-lg font-semibold text-white">Configure the first composition</h2>
        <p className="mx-auto mt-3 max-w-md text-[11px] leading-5 text-muted">
          Choose the Agent that will receive requests for this Network. The first Agent is automatically defined as the entry point.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {hasAgents ? (
            <button type="button" disabled={pending} onClick={onChooseAgent} className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-[10px] font-semibold text-white shadow-lg shadow-primary/20 disabled:cursor-not-allowed disabled:opacity-45">
              <Bot className="h-3.5 w-3.5" />Choose existing Agent
            </button>
          ) : null}
          <button type="button" disabled={pending} onClick={onCreateAgent} className={cn(secondaryAction, !hasAgents && 'border-primary/30 bg-primary text-white shadow-lg shadow-primary/20 hover:bg-primary')}>
            <Plus className="h-3.5 w-3.5" />{hasAgents ? 'Create new Agent' : 'Create first Agent'}
          </button>
        </div>
        <div className="mt-6 rounded-xl border border-border/80 bg-background/35 px-4 py-3 text-left">
          <p className="text-[10px] font-medium text-slate-200">Start simple</p>
          <p className="mt-1 text-[9px] leading-4 text-muted">A Network with one entry Agent is valid. Specialists and delegations can be added after the first test.</p>
        </div>
      </section>
    </div>
  )
}

export function NetworkInitialSetupInspector() {
  return (
    <aside className="absolute inset-y-0 right-0 z-40 flex min-h-0 w-[min(94vw,420px)] shrink-0 flex-col border-l border-border bg-surface/95 shadow-2xl shadow-black/30 xl:relative xl:z-auto xl:w-[420px] xl:bg-surface/80 xl:shadow-none">
      <header className="border-b border-border p-5">
        <p className="text-[8px] font-semibold uppercase tracking-[0.18em] text-primary-light">Network setup</p>
        <h2 className="mt-2 text-sm font-semibold text-white">Prepare the first executable Draft</h2>
        <p className="mt-2 text-[10px] leading-5 text-muted">Only the decisions required for the first test are shown at this stage.</p>
      </header>
      <div className="space-y-3 p-5">
        {[
          ['1', 'Choose the entry Agent', 'Select an existing Agent or create one without leaving the Network.'],
          ['2', 'Save the composition', 'The first node and entry point are persisted together.'],
          ['3', 'Run the first test', 'A Draft session is created only when you explicitly start testing.'],
        ].map(([number, title, description]) => (
          <section key={number} className="flex gap-3 rounded-xl border border-border bg-background/30 p-3.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-[10px] font-semibold text-primary-light">{number}</span>
            <div>
              <p className="text-[10px] font-medium text-white">{title}</p>
              <p className="mt-1 text-[9px] leading-4 text-muted">{description}</p>
            </div>
          </section>
        ))}
        <section className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3.5">
          <div className="flex items-center gap-2 text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" /><p className="text-[10px] font-medium">Specialists are optional</p></div>
          <p className="mt-2 text-[9px] leading-4 text-emerald-100/70">The entry Agent can execute the Network alone. Add delegation only when the use case requires it.</p>
        </section>
      </div>
    </aside>
  )
}

export function NetworkReadyToTest({
  pending,
  onTest,
  onAddSpecialist,
}: {
  pending: boolean
  onTest: () => void
  onAddSpecialist: () => void
}) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-6 z-20 flex justify-center px-6">
      <section className="pointer-events-auto flex max-w-2xl items-center gap-4 rounded-2xl border border-primary/25 bg-surface/95 px-5 py-4 shadow-2xl shadow-black/35 backdrop-blur">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><CheckCircle2 className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold text-white">Network ready for the first test</p>
          <p className="mt-1 text-[9px] leading-4 text-muted">Validate the entry Agent before expanding the composition.</p>
        </div>
        <button type="button" disabled={pending} onClick={onAddSpecialist} className={secondaryAction}><Plus className="h-3.5 w-3.5" />Add specialist</button>
        <button type="button" disabled={pending} onClick={onTest} className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"><MessageSquare className="h-3.5 w-3.5" />{pending ? 'Preparing…' : 'Test Network'}</button>
      </section>
    </div>
  )
}
