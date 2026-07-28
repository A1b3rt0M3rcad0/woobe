import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { usePlans, useOrganizationSubscription } from '@/features/billing/hooks'
import { useOrganization } from '@/features/organizations/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { GuidedEmptyState } from '@/components/common/GuidedEmptyState'
import { ResourceSummaryCard } from '@/components/common/ResourceSummaryCard'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatDate } from '@/lib/formatters/date'
import { Check, CreditCard, ShieldCheck, WalletCards } from 'lucide-react'
import type { Plan } from '@/features/billing/types'

export default function BillingPage() {
  const { organizationId } = useParams<{ organizationId: string }>()
  const { currentOrganization, selectOrganization } = useWorkspace()
  const {
    data: organization,
    isLoading: organizationLoading,
    isError: organizationError,
    error: organizationErrorValue,
    refetch: refetchOrganization,
  } = useOrganization(organizationId)
  const { data: plans, isLoading: plansLoading, isError: plansError, refetch: refetchPlans } = usePlans()
  const { data: subscription, isLoading: subLoading } = useOrganizationSubscription(organizationId)

  useEffect(() => {
    if (!organization || currentOrganization?.id === organization.id) return
    selectOrganization({ id: organization.id, name: organization.name, slug: organization.slug })
  }, [currentOrganization, organization, selectOrganization])

  if (!organizationId) return <ErrorState message="Organization not found" />
  if (organizationLoading || plansLoading || subLoading) return <LoadingState />
  if (organizationError) return <ErrorState error={organizationErrorValue} onRetry={refetchOrganization} />
  if (plansError) return <ErrorState onRetry={refetchPlans} />
  if (!organization) return <ErrorState message="Organization not found" />

  const planItems = plans ?? []
  const currentPlan = planItems.find((plan) => plan.id === subscription?.plan_id)

  return (
    <div className="space-y-6">
      <PageHeader title="Billing" description={`Manage subscription status, plans and limits for ${organization.name}.`} />

      <div className="grid gap-4 md:grid-cols-3">
        <ResourceSummaryCard label="Organization" value={organization.name} detail="Billing context" icon={<WalletCards className="h-5 w-5" />} />
        <ResourceSummaryCard label="Current plan" value={currentPlan?.name || 'Pending'} detail={subscription?.status || 'Billing not connected'} icon={<CreditCard className="h-5 w-5" />} />
        <ResourceSummaryCard label="Status" value={subscription?.status || 'Pending'} detail="Subscription state" icon={<ShieldCheck className="h-5 w-5" />} />
      </div>

      {subscription ? (
        <Card>
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
      ) : (
        <GuidedEmptyState
          icon={<CreditCard className="h-6 w-6" />}
          title="Billing integration pending"
          description="Subscription management will appear here once billing is connected for this organization."
          next={["Review available plans", "Connect billing", "Monitor limits"]}
        />
      )}

      {planItems.length > 0 ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {planItems.map((plan: Plan) => (
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
      ) : (
        <GuidedEmptyState
          icon={<CreditCard className="h-6 w-6" />}
          title="No plans available"
          description="Plans are not configured yet. Contact support for pricing and account setup."
        />
      )}
    </div>
  )
}
