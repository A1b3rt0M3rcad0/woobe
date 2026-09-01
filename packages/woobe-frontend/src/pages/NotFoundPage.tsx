import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md rounded-2xl border border-border/90 bg-surface/80 p-8 text-center shadow-2xl shadow-black/20">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Not found</p>
        <h1 className="mt-3 text-6xl font-semibold tracking-tight text-white">404</h1>
        <p className="mt-4 text-sm leading-6 text-muted">This route does not exist in the current product surface.</p>
        <Link
          to="/dashboard"
          className="mt-6 inline-flex h-9 items-center rounded-lg bg-primary px-4 text-sm font-medium text-white transition-colors hover:bg-primary-hover"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  )
}
