import { Bot, BookOpen, Wrench, MessageSquare, Key, BarChart3, CreditCard, Activity, Shield, Zap } from 'lucide-react'

const features = [
  { icon: Bot, title: 'Agent Runtime', description: 'Run AI agents with configurable models, system prompts, and session management.' },
  { icon: BookOpen, title: 'RAG Knowledge', description: 'Upload documents, parse, chunk, embed, and retrieve relevant content for your agents.' },
  { icon: Wrench, title: 'Tool Calling', description: 'Connect agents to external APIs via HTTP MCP tools with secrets management.' },
  { icon: MessageSquare, title: 'Session Management', description: 'Managed, external, or stateless sessions with full message history.' },
  { icon: Key, title: 'API Keys', description: 'Secure API key authentication with scoped access for external integrations.' },
  { icon: BarChart3, title: 'Usage Metering', description: 'Track requests, tokens, tool calls, vector queries, and estimated costs.' },
  { icon: CreditCard, title: 'Billing Ready', description: 'Plan-based billing with subscription management and usage limits.' },
  { icon: Activity, title: 'Observability', description: 'Full traces with events, latency, cost, and error tracking per request.' },
  { icon: Shield, title: 'BYOK Credentials', description: 'Bring your own API keys for OpenAI, Anthropic, Google, and custom providers.' },
  { icon: Zap, title: 'Event-driven', description: 'Outbox/inbox event propagation for reliable async processing.' },
]

export function FeatureGrid() {
  return (
    <section id="features" className="py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-white">Everything you need to run AI agents in production</h2>
          <p className="mt-3 text-muted">No more building infrastructure. Just create, configure, and deploy.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-surface p-6 hover:border-primary/50 transition-colors">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <f.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="mt-4 font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-muted">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
