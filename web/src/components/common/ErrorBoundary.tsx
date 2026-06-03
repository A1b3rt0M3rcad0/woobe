import { Component, type ReactNode, type ErrorInfo } from 'react'
import { AlertTriangle, RefreshCw, ArrowLeft } from 'lucide-react'
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
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <AlertTriangle className="h-10 w-10 text-red-400" />
          <h3 className="mt-3 text-lg font-semibold text-white">Something went wrong</h3>
          <p className="mt-1 text-sm text-muted max-w-md">
            An unexpected error occurred. Please try again or return to the dashboard.
          </p>
          <div className="flex gap-3 mt-4">
            <Button variant="outline" size="sm" onClick={this.handleReload}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Reload
            </Button>
            <Button variant="outline" size="sm" onClick={this.handleBackToDashboard}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to dashboard
            </Button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
