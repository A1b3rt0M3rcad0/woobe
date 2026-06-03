import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { ArrowRight, CheckCircle2 } from 'lucide-react'

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20">
      <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent" />
      <div className="relative mx-auto max-w-7xl px-6 text-center">
        <h1 className="text-5xl font-bold tracking-tight text-white sm:text-6xl">
          Production runtime for AI agents.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted">
          Build, test, and run AI agents with RAG, tools, sessions, API keys, usage tracking, and observability — without rebuilding the infrastructure from scratch.
        </p>

        <div className="mt-8 flex items-center justify-center gap-4">
          <Link to="/register">
            <Button size="lg" className="text-base">
              Start building
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
          <Link to="/register">
            <Button variant="outline" size="lg" className="text-base">
              Try playground
            </Button>
          </Link>
        </div>

        <div className="mt-12 mx-auto max-w-3xl rounded-xl border border-border bg-surface p-6 text-left">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-muted">Agent configured</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-muted">RAG enabled</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-muted">Tool calls</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-muted">Usage tracked</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-muted">Trace completed</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-muted">API ready</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
