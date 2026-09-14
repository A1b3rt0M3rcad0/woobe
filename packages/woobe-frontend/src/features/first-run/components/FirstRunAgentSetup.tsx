import { ArrowLeft, ArrowRight, Bot, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useAgentCreationFlow, type AgentCreationStep } from '@/features/agents/hooks/useAgentCreationFlow'
import type { Agent } from '@/features/agents/types'
import { AgentDetailsStep } from './AgentDetailsStep'
import { AgentModelStep } from './AgentModelStep'
import { AgentReviewStep } from './AgentReviewStep'

interface FirstRunAgentSetupProps { projectId: string; onCreated: (agent: Agent) => void }

const stepCopy: Record<AgentCreationStep, { title: string; description: string }> = {
  details: { title: 'Define the Agent', description: 'Set its identity and initial behavior before choosing the model.' },
  model: { title: 'Choose the Agent model', description: 'Use an existing Project model or add one through a provider connection.' },
  review: { title: 'Review and create', description: 'Confirm the Agent instructions and model binding before opening the Playground.' },
}

export function firstRunAgentStepCopy(step: AgentCreationStep) { return stepCopy[step] }

export function FirstRunAgentSetup({ projectId, onCreated }: FirstRunAgentSetupProps) {
  const flow = useAgentCreationFlow({ projectId, onCreated })
  const copy = stepCopy[flow.step]

  const primaryAction = () => {
    if (flow.step === 'details') return <Button type="button" onClick={flow.continueFromDetails} disabled={flow.inventoryLoading}>Continue<ArrowRight className="ml-1.5 h-3.5 w-3.5" /></Button>
    if (flow.step === 'model') return <Button type="button" onClick={() => { void flow.continueFromModel() }} loading={flow.creatingModel} disabled={!flow.canContinueModel}>{flow.modelMode === 'existing' ? 'Continue to review' : 'Add model and review'}<ArrowRight className="ml-1.5 h-3.5 w-3.5" /></Button>
    return <Button type="button" onClick={() => { void flow.createAgent() }} loading={flow.creatingAgent}><ShieldCheck className="mr-1.5 h-3.5 w-3.5" />Create Agent and open Playground</Button>
  }

  return (
    <section className="grid min-h-[480px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-container border border-border bg-surface/55 lg:h-full lg:min-h-0">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4 sm:px-6">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Bot className="h-3.5 w-3.5" /></div>
        <div className="min-w-0"><p className="font-mono text-[9px] uppercase tracking-[0.16em] text-primary-light">Agent setup / {flow.stepNumber} of 3</p><h2 className="mt-1 font-mono text-[13px] font-semibold text-slate-100">{copy.title}</h2><p className="mt-1 max-w-2xl font-sans text-xs leading-5 text-muted">{copy.description}</p></div>
      </header>
      {flow.step === 'model' ? <div className="min-h-0 overflow-hidden px-5 py-4 sm:px-6"><AgentModelStep projectId={projectId} flow={flow} /></div> : <ScrollArea className="min-h-0 px-5 py-5 sm:px-6">{flow.step === 'details' ? <AgentDetailsStep flow={flow} /> : <AgentReviewStep flow={flow} />}</ScrollArea>}
      <footer className="flex min-h-[52px] items-center justify-between gap-3 border-t border-border px-5 py-3 sm:px-6"><div>{flow.step !== 'details' ? <Button type="button" size="sm" variant="outline" onClick={flow.goBack} disabled={flow.busy}><ArrowLeft className="mr-1.5 h-3.5 w-3.5" />Back</Button> : null}</div>{primaryAction()}</footer>
    </section>
  )
}
