import { get } from '@/lib/api/client'
import type { Plan, Subscription } from './types'

export async function getPlans(): Promise<Plan[]> {
  return get<Plan[]>('/billing/plans')
}

export async function getOrganizationSubscription(orgId: string): Promise<Subscription> {
  return get<Subscription>(`/billing/organizations/${orgId}/subscription`)
}
