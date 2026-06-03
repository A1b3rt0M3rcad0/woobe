import { Button } from '@/components/ui/Button'
import { Check } from 'lucide-react'
import { Link } from 'react-router-dom'

const plans = [
  {
    name: 'Demo / Free',
    price: 'Free',
    description: 'For testing and small experiments',
    features: ['1 agent', '100 messages/day', '5MB documents', '24h traces', 'No integrations'],
    cta: 'Get started',
    popular: false,
  },
  {
    name: 'Starter',
    price: '$99',
    period: '/mo',
    description: 'For production deployments',
    features: ['API access', 'RAG enabled', 'Tools support', 'Usage dashboard', 'Basic traces', 'Up to 5 agents'],
    cta: 'Start trial',
    popular: true,
  },
  {
    name: 'Growth',
    price: '$299',
    period: '/mo',
    description: 'For scaling teams',
    features: ['More projects', 'More agents', 'Longer retention', 'Higher limits', 'Priority support', 'Custom integrations'],
    cta: 'Contact sales',
    popular: false,
  },
]

export function PricingSection() {
  return (
    <section id="pricing" className="py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-white">Simple, transparent pricing</h2>
          <p className="mt-3 text-muted">Start free, scale as you grow.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-xl border p-6 ${
                plan.popular
                  ? 'border-primary bg-primary/5'
                  : 'border-border bg-surface'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-0.5 text-xs font-medium text-white">
                  Most popular
                </div>
              )}
              <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
              <div className="mt-3">
                <span className="text-3xl font-bold text-white">{plan.price}</span>
                {plan.period && <span className="text-sm text-muted">{plan.period}</span>}
              </div>
              <p className="mt-2 text-sm text-muted">{plan.description}</p>
              <ul className="mt-6 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-muted">
                    <Check className="h-4 w-4 text-primary" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link to="/register">
                <Button
                  variant={plan.popular ? 'default' : 'outline'}
                  className="mt-6 w-full"
                >
                  {plan.cta}
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
