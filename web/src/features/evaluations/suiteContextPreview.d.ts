import './types'

declare module './types' {
  interface SuiteContextPreview {
    requested_case_count?: number
    estimated_batch_count?: number
    estimated_total_cost_usd?: number | null
    estimated_maximum_provider_calls?: number
  }
}
