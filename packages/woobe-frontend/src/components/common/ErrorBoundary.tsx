import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react'
import { Button, EmptyStatePanel } from '@woobe/ui'

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
          icon={<AlertTriangle className="h-icon-lg w-icon-lg text-error" />}
          title="Something went wrong"
          description="An unexpected error occurred. Try again or return to the dashboard."
          action={(
            <div className="flex flex-wrap justify-center gap-ui-sm">
              <Button variant="outline" size="sm" onClick={this.handleReload}>
                <RefreshCw className="mr-ui-xs h-icon-sm w-icon-sm" />Reload
              </Button>
              <Button variant="outline" size="sm" onClick={this.handleBackToDashboard}>
                <ArrowLeft className="mr-ui-xs h-icon-sm w-icon-sm" />Back to dashboard
              </Button>
            </div>
          )}
        />
      )
    }

    return this.props.children
  }
}
