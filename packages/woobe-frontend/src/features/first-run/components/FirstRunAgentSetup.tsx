import { useEffect, useRef } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { Button } from '@woobe/ui'
import { useAgentCreationFlow, type AgentCreationStep } from '@/features/agents/hooks/useAgentCreationFlow'
import type { Agent } from '@/features/agents/types'
import { AgentDetailsStep } from './AgentDetailsStep'
import { AgentModelStep } from './AgentModelStep'
import { AgentReviewStep } from './AgentReviewStep'

export interface FirstRunAgentState { step: AgentCreationStep; dirty: boolean; busy: boolean }
interface FirstRunAgentSetupProps { projectId: string; onCreated: (agent: Agent) => void; onStateChange?: (state: FirstRunAgentState) => void }
const stepCopy: Record<AgentCreationStep, { title: string; description: string }> = {
  details: { title: 'Give your Agent a purpose', description: 'Start with its name and the task it should help with. You can refine these later.' },
  model: { title: 'Choose a model', description: 'Reuse a Project model or connect a provider and add one. Your instructions stay here.' },
  review: { title: 'Review your Agent', description: 'Check the instructions and model before creating a Draft.' },
}
export function firstRunAgentStepCopy(step: AgentCreationStep) { return stepCopy[step] }

export function FirstRunAgentSetup({ projectId, onCreated, onStateChange }: FirstRunAgentSetupProps) {
  const flow = useAgentCreationFlow({ projectId, onCreated })
  const panel = useRef<HTMLElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const dirty = Boolean(flow.agentName || flow.agentObjective || flow.agentDescription)
  useEffect(() => { onStateChange?.({ step: flow.step, dirty, busy: flow.busy }) }, [flow.step, dirty, flow.busy, onStateChange])
  useEffect(() => { if (flow.step !== 'details') heading.current?.focus() }, [flow.step])
  const copy = stepCopy[flow.step]
  const action = flow.step === 'details' ? 'Choose model' : flow.step === 'model' ? flow.modelMode === 'existing' ? 'Review Agent' : 'Save model and review' : 'Create Agent Draft'
  const next = () => {
    if (flow.step === 'details') {
      if (!flow.continueFromDetails()) requestAnimationFrame(() => panel.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
    } else if (flow.step === 'model') void flow.continueFromModel()
    else void flow.createAgent()
  }
  return (
    <section ref={panel} aria-labelledby="first-agent-step-title" className="overflow-hidden rounded-container border border-border bg-surface">
      <header className="border-b border-border px-5 py-5 sm:px-6">
        <h2 id="first-agent-step-title" ref={heading} tabIndex={-1} className="font-serif text-editorial-section font-normal text-foreground outline-none">{copy.title}</h2>
        <p className="mt-2 text-sm leading-5 text-muted-foreground">{copy.description}</p>
      </header>
        <div className="px-5 py-6 sm:px-6">
          {flow.step === 'details' ? <form id="first-agent-details" onSubmit={event => { event.preventDefault(); next() }} noValidate><AgentDetailsStep flow={flow} /></form> : flow.step === 'model' ? <AgentModelStep projectId={projectId} flow={flow} /> : <AgentReviewStep flow={flow} />}
          {flow.submissionError && <p role="alert" className="mt-4 text-sm text-error">{flow.submissionError}</p>}
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4 sm:px-6">
          <div>{flow.step !== 'details' ? <Button type="button" size="sm" variant="outline" onClick={flow.goBack} disabled={flow.busy}><ArrowLeft className="h-3.5 w-3.5" />Back</Button> : <p className="text-xs text-muted-foreground">Your Agent is created after review.</p>}</div>
          <Button type={flow.step === 'details' ? 'submit' : 'button'} form={flow.step === 'details' ? 'first-agent-details' : undefined} onClick={flow.step === 'details' ? undefined : next} loading={flow.busy} disabled={flow.step === 'model' && (!flow.canContinueModel || flow.inventoryLoading || flow.inventoryError)}>{action}<ArrowRight className="h-3.5 w-3.5" /></Button>
        </footer>
    </section>
  )
}
