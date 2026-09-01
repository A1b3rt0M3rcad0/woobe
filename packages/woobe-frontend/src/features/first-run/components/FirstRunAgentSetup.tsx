import { ArrowLeft, ArrowRight, Bot, ShieldCheck } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useAgentCreationFlow, type AgentCreationStep } from '@/features/agents/hooks/useAgentCreationFlow'
import type { Agent } from '@/features/agents/types'
import { AgentDetailsStep } from './AgentDetailsStep'
import { AgentModelStep } from './AgentModelStep'
import { AgentReviewStep } from './AgentReviewStep'

interface FirstRunAgentSetupProps {
  projectId: string
  onCreated: (agent: Agent) => void
}

const stepCopy: Record<AgentCreationStep, { title: string; description: string }> = {
  details: {
    title: 'Define the Agent',
    description: 'Set its identity and initial behavior before choosing the model.',
  },
  model: {
    title: 'Choose the Agent model',
    description: 'Use an existing Project model or add one through a provider connection.',
  },
  review: {
    title: 'Review and create',
    description: 'Confirm the Agent instructions and model binding before opening the Playground.',
  },
}

export function firstRunAgentStepCopy(step: AgentCreationStep) {
  return stepCopy[step]
}

export function FirstRunAgentSetup({ projectId, onCreated }: FirstRunAgentSetupProps) {
  const flow = useAgentCreationFlow({ projectId, onCreated })
  const copy = stepCopy[flow.step]

  const primaryAction = () => {
    if (flow.step === 'details') {
      return (
        <Button type="button" onClick={flow.continueFromDetails} disabled={flow.inventoryLoading}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )
    }

    if (flow.step === 'model') {
      return (
        <Button
          type="button"
          onClick={() => { void flow.continueFromModel() }}
          loading={flow.creatingModel}
          disabled={!flow.canContinueModel}
        >
          {flow.modelMode === 'existing' ? 'Continue to review' : 'Add model and review'}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )
    }

    return (
      <Button type="button" onClick={() => { void flow.createAgent() }} loading={flow.creatingAgent}>
        <ShieldCheck className="mr-2 h-4 w-4" />
        Create Agent and open Playground
      </Button>
    )
  }

  return (
    <section className="grid min-h-[620px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-2xl border border-border/90 bg-surface/60 shadow-xl shadow-black/10 lg:h-full lg:min-h-0">
      <header className="border-b border-border/80 px-6 py-5 sm:px-8">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <Bot className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-primary-light">
              Agent setup · Step {flow.stepNumber} of 3
            </p>
            <h2 className="mt-1.5 text-xl font-semibold text-white">{copy.title}</h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">{copy.description}</p>
          </div>
        </div>
      </header>

      {flow.step === 'model' ? (
        <div className="min-h-0 overflow-hidden px-6 py-5 sm:px-8">
          <AgentModelStep projectId={projectId} flow={flow} />
        </div>
      ) : (
        <ScrollArea className="min-h-0 px-6 py-6 sm:px-8">
          {flow.step === 'details' ? <AgentDetailsStep flow={flow} /> : <AgentReviewStep flow={flow} />}
        </ScrollArea>
      )}

      <footer className="flex min-h-[68px] items-center justify-between gap-3 border-t border-border/80 px-6 py-4 sm:px-8">
        <div>
          {flow.step !== 'details' && (
            <Button type="button" variant="outline" onClick={flow.goBack} disabled={flow.busy}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          )}
        </div>
        {primaryAction()}
      </footer>
    </section>
  )
}
