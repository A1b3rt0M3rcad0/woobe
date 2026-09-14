import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button, EmptyStatePanel } from '@woobe/ui'
import { ApiError } from '@/lib/api/errors'

interface ErrorStateProps {
  error?: Error | ApiError | null
  message?: string
  onRetry?: () => void
  className?: string
}

export function ErrorState({ error, message, onRetry, className }: ErrorStateProps) {
  const displayMessage = message || error?.message || 'Something went wrong'
  const status = error instanceof ApiError ? error.status : null

  return (
    <EmptyStatePanel
      className={className}
      icon={<AlertCircle className="h-icon w-icon text-error" />}
      title="Error"
      description={(
        <div>
          <p>{displayMessage}</p>
          {status ? <p className="mt-ui-xs font-mono text-system-label text-muted-foreground">HTTP {status}</p> : null}
        </div>
      )}
      action={onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-icon-sm w-icon-sm" />
          Try again
        </Button>
      ) : undefined}
    />
  )
}
