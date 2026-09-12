import { Bot, Plus } from 'lucide-react'
import { Button, GuidedEmptyState } from '@woobe/ui'

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
      className="grid min-w-0 flex-1 place-items-center overflow-hidden bg-background px-4 py-6"
      aria-label="Network initial setup"
    >
      <GuidedEmptyState
        className="w-full max-w-xl bg-surface/55"
        icon={<Bot className="h-4 w-4" />}
        title="Choose the entry Agent"
        description="This Agent receives the requests sent to the Network. You can add specialists and delegation paths after validating the first test."
        actionLabel={hasAgents ? 'Choose Agent' : 'Create first Agent'}
        onAction={hasAgents ? onChooseAgent : onCreateAgent}
        secondaryAction={hasAgents ? (
          <Button type="button" variant="outline" disabled={pending} onClick={onCreateAgent}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Create new Agent
          </Button>
        ) : undefined}
        next={[
          'The first node and entry point are persisted together.',
          'A single entry Agent already creates a valid Network for testing.',
        ]}
      />
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
