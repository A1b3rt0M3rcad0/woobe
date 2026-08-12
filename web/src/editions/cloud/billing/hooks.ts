import { useQuery } from '@tanstack/react-query'
import { getPlans, getOrganizationSubscription } from './api'

export function usePlans() {
  return useQuery({
    queryKey: ['plans'],
    queryFn: () => getPlans(),
  })
}

export function useOrganizationSubscription(orgId: string | undefined) {
  return useQuery({
    queryKey: ['subscription', orgId],
    queryFn: () => getOrganizationSubscription(orgId!),
    enabled: Boolean(orgId),
  })
}
