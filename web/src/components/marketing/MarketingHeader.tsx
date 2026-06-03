import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Play } from 'lucide-react'

export function MarketingHeader() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Play className="h-4 w-4 text-white" />
          </div>
          <span className="text-lg font-semibold text-white">ProjectRAI</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          <a href="#features" className="text-sm text-muted hover:text-white transition-colors">Features</a>
          <a href="#pricing" className="text-sm text-muted hover:text-white transition-colors">Pricing</a>
          <a href="#docs" className="text-sm text-muted hover:text-white transition-colors">Docs</a>
        </nav>

        <div className="flex items-center gap-3">
          <Link to="/login">
            <Button variant="ghost" size="sm">Login</Button>
          </Link>
          <Link to="/register">
            <Button size="sm">Start building</Button>
          </Link>
        </div>
      </div>
    </header>
  )
}
