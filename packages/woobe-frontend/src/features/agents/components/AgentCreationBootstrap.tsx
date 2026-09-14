import { Loader2, RefreshCw } from 'lucide-react'
import { Button, EmptyStatePanel, Skeleton } from '@woobe/ui'

export function AgentCreationPreparing() {
  return (
    <div className="grid min-h-80 grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
      <div className="mb-ui-md grid grid-cols-3 gap-ui-sm rounded-container border border-border bg-background/35 p-ui-sm" aria-hidden="true">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="flex items-center gap-ui-sm rounded-control px-ui-md py-ui-sm">
            <Skeleton className="h-control-xs w-control-xs rounded-full" />
            <Skeleton className="h-ui-sm w-20" />
          </div>
        ))}
      </div>

      <div className="flex min-h-0 flex-col items-center justify-center rounded-container border border-border bg-surface/65 px-ui-xl py-ui-lg text-center" role="status" aria-live="polite" aria-busy="true">
        <div className="flex h-control-lg w-control-lg items-center justify-center rounded-control border border-primary/30 bg-primary/[0.08] text-primary-light">
          <Loader2 className="h-icon-lg w-icon-lg animate-spin" />
        </div>
        <p className="mt-ui-md font-sans text-product-body font-semibold text-accent-foreground">Preparing Agent setup</p>
        <p className="mt-ui-sm max-w-md font-sans text-product-small text-muted-foreground">
          Loading Provider connections and generation models for this Project.
        </p>

        <div className="mt-ui-lg grid w-full max-w-xl gap-ui-sm" aria-hidden="true">
          <Skeleton className="h-control-row w-full" />
          <Skeleton className="h-control-row w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
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
