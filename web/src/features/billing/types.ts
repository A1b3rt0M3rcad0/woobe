export interface Plan {
  id: string
  code: string
  name: string
  price_usd: number
  status?: string
  limits?: Record<string, unknown>
}

export interface Subscription {
  id: string
  organization_id: string
  plan_id: string
  status: string
  current_period_end?: string
}
