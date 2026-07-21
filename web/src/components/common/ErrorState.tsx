import { cn } from '@/lib/utils'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ApiError } from '@/lib/api/errors'

interface ErrorStateProps {
  error?: Error | ApiError | null
  title?: string
  description?: string
  message?: string
  onRetry?: () => void
  className?: string
}

export function ErrorState({
  error,
  title = 'Error',
  description,
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  const displayMessage = description || message || error?.message || 'Something went wrong'
  const status = error instanceof ApiError ? error.status : null

  return (
    <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
      <AlertCircle className="h-10 w-10 text-red-400" />
      <h3 className="mt-3 text-lg font-semibold text-white">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted">{displayMessage}</p>
      {status && <p className="mt-1 text-xs text-muted">Status: {status}</p>}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try again
        </Button>
      )}
    </div>
  )
}
