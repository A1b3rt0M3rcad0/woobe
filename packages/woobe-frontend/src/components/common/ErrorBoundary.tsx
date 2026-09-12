import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react'
import { EmptyStatePanel } from '@woobe/ui'
import { Button } from '@/components/ui/Button'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo)
    this.props.onError?.(error, errorInfo)
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null })
  }

  handleBackToDashboard = () => {
    window.location.href = '/dashboard'
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <EmptyStatePanel
          icon={<AlertTriangle className="h-4 w-4 text-red-300" />}
          title="Something went wrong"
          description="An unexpected error occurred. Try again or return to the dashboard."
          action={(
            <div className="flex flex-wrap justify-center gap-2">
              <Button variant="outline" size="sm" onClick={this.handleReload}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />Reload
              </Button>
              <Button variant="outline" size="sm" onClick={this.handleBackToDashboard}>
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />Back to dashboard
              </Button>
            </div>
          )}
        />
      )
    }

    return this.props.children
  }
}
