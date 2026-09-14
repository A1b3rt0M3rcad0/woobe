import { RefreshCw } from 'lucide-react'
import { Button, EmptyStatePanel, LoadingState } from '@woobe/ui'

export function AgentCreationPreparing() {
  return (
    <div className="min-h-80">
      <LoadingState
        variant="panel"
        layout="list"
        message="Preparing Agent setup"
        description="Loading Provider connections and generation models for this Project."
        delayMs={0}
      />
    </div>
  )
}

export function AgentCreationLoadError({ onRetry, onCancel }: { onRetry: () => void; onCancel: () => void }) {
  return (
    <div className="flex min-h-80 items-center justify-center">
      <EmptyStatePanel
        icon={<RefreshCw className="h-icon-lg w-icon-lg" />}
        title="Could not prepare Agent setup"
        description="The Project Provider connections or generation models could not be loaded. No Agent data was changed."
        action={(
          <div className="flex flex-col justify-center gap-ui-sm sm:flex-row">
            <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
            <Button type="button" onClick={onRetry}>
              <RefreshCw className="h-icon w-icon" />Retry
            </Button>
          </div>
        )}
        className="w-full max-w-xl border-error/25 bg-error/[0.04]"
      />
    </div>
  )
}
