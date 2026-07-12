import { useEffect, useState } from 'react'
import { Bot, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Textarea } from '@/components/ui/Textarea'
import { useUpdateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'

interface FirstAgentInstructionsDialogProps {
  open: boolean
  agent: Agent | null
  onComplete: (agent: Agent) => void
}

function defaultInstructions(agent: Agent) {
  const description = agent.description?.trim()
  if (description) return description
  return `You are ${agent.name}. Help users clearly and accurately within your configured purpose.`
}

export function FirstAgentInstructionsDialog({ open, agent, onComplete }: FirstAgentInstructionsDialogProps) {
  const updateAgent = useUpdateAgent(agent?.id)
  const [instructions, setInstructions] = useState('')

  useEffect(() => {
    if (!open || !agent) return
    setInstructions(agent.system_prompt?.trim() || defaultInstructions(agent))
  }, [agent, open])

  const openPlayground = () => {
    if (agent) onComplete(agent)
  }

  const handleSave = async () => {
    if (!agent) return
    const normalizedInstructions = instructions.trim()
    if (!normalizedInstructions) {
      toast.error('Agent instructions are required')
      return
    }

    try {
      await updateAgent.mutateAsync({ system_prompt: normalizedInstructions })
      toast.success('Agent instructions saved')
      onComplete({ ...agent, system_prompt: normalizedInstructions })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save Agent instructions')
    }
  }

  return (
    <Dialog open={open} onClose={updateAgent.isPending ? () => undefined : openPlayground} title="Set Agent instructions" className="max-w-2xl">
      <div className="space-y-5">
        <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
              <Bot className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-white">Define the initial behavior</h3>
              <p className="mt-1 text-xs leading-5 text-muted">These instructions initialize the current Draft. Advanced settings remain available in the Playground.</p>
            </div>
          </div>

          <div className="mt-4">
            <label className="mb-1 block text-sm font-medium text-muted" htmlFor="first-agent-instructions">Instructions</label>
            <Textarea
              id="first-agent-instructions"
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              rows={7}
              placeholder="You are a customer support Agent for..."
              autoFocus
            />
          </div>
        </section>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button type="button" variant="ghost" onClick={openPlayground} disabled={updateAgent.isPending}>
            Configure in Playground
          </Button>
          <Button type="button" onClick={handleSave} loading={updateAgent.isPending} disabled={!instructions.trim()}>
            Save and open Playground
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
