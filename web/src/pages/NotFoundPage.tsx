import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-white">404</h1>
        <p className="mt-4 text-lg text-muted">Page not found</p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover transition-colors"
        >
          Go home
        </Link>
      </div>
    </div>
  )
}
