import { Play } from 'lucide-react'
import { Link } from 'react-router-dom'

export function Footer() {
  return (
    <footer className="border-t border-border py-12">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Play className="h-4 w-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">ProjectRAI</span>
          </div>
          <nav className="flex items-center gap-6">
            <Link to="/" className="text-sm text-muted hover:text-white transition-colors">Home</Link>
            <a href="#features" className="text-sm text-muted hover:text-white transition-colors">Features</a>
            <a href="#pricing" className="text-sm text-muted hover:text-white transition-colors">Pricing</a>
            <Link to="/login" className="text-sm text-muted hover:text-white transition-colors">Login</Link>
          </nav>
          <p className="text-xs text-muted">2026 ProjectRAI. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}
