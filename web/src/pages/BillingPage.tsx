import { usePlans, useOrganizationSubscription } from '@/features/billing/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatDate } from '@/lib/formatters/date'
import { Check, CreditCard } from 'lucide-react'
import type { Plan } from '@/features/billing/types'

export default function BillingPage() {
  const { currentOrganization } = useWorkspace()
  const { data: plans, isLoading: plansLoading, isError: plansError, refetch: refetchPlans } = usePlans()
  const { data: subscription, isLoading: subLoading } = useOrganizationSubscription(currentOrganization?.id)

  if (plansLoading || subLoading) return <LoadingState />
  if (plansError) return <ErrorState onRetry={refetchPlans} />

  return (
    <div>
      <PageHeader title="Billing" description="Manage your subscription and plan" />

      {subscription && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Current Plan
              <Badge variant={subscription.status === 'active' ? 'success' : 'secondary'}>
                {subscription.status}
              </Badge>
            </CardTitle>
            <CardDescription>
              {subscription.current_period_end
                ? `Current period ends ${formatDate(subscription.current_period_end)}`
                : 'Subscription active'}
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {!subscription && (
        <Card className="mb-8">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <CreditCard className="h-6 w-6 text-muted" />
              <div>
                <p className="font-medium text-white">Billing integration pending</p>
                <p className="text-sm text-muted">Subscription management will be available once billing is fully connected.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {plans && plans.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl">
          {plans.map((plan: Plan) => (
            <Card key={plan.id} className={plan.code === 'starter' ? 'border-primary' : ''}>
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>
                  <span className="text-2xl font-bold text-white">${plan.price_usd}</span>
                  <span className="text-sm text-muted">/month</span>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {plan.limits && Object.entries(plan.limits).map(([key, val]) => (
                    <div key={key} className="flex items-center gap-2 text-sm text-muted">
                      <Check className="h-4 w-4 text-primary" />
                      {key}: {String(val)}
                    </div>
                  ))}
                </div>
              </CardContent>
              <CardFooter>
                <Button variant={plan.code === 'starter' ? 'default' : 'outline'} className="w-full">
                  {subscription?.plan_id === plan.id ? 'Current plan' : subscription ? 'Upgrade' : 'Get started'}
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {(!plans || plans.length === 0) && (
        <Card>
          <CardContent className="p-6 text-center text-muted">
            No plans available. Contact support for pricing.
          </CardContent>
        </Card>
      )}
    </div>
  )
}
