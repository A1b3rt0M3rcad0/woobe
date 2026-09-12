import { AlertCircle, RefreshCw } from 'lucide-react'
import { EmptyStatePanel } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
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
      icon={<AlertCircle className="h-4 w-4 text-red-300" />}
      title="Error"
      description={(
        <div>
          <p>{displayMessage}</p>
          {status ? <p className="mt-1 font-mono text-[10px] text-muted-foreground">HTTP {status}</p> : null}
        </div>
      )}
      action={onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Try again
        </Button>
      ) : undefined}
    />
  )
}
