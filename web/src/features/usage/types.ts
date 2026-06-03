export interface DailyUsage {
  project_id: string
  day: string
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
}
