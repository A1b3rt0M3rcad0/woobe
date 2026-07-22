import './types'

interface EvaluationTargetManifest {
  identity?: Record<string, unknown>
  model?: Record<string, unknown>
  prompt?: Record<string, unknown>
  tools?: Array<Record<string, unknown>>
  knowledge?: Record<string, unknown>
  output_contract?: Record<string, unknown>
  runtime?: Record<string, unknown>
  network?: Record<string, unknown>
}

interface EvaluationDecisionPayload {
  id: string
  evaluation_run_id: string
  target_id: string
  target_snapshot_hash: string
  decision: 'accepted' | 'rejected'
  note?: string | null
  decided_by: string
  decided_at: string
}

declare module './types' {
  interface EvaluationTarget {
    manifest?: EvaluationTargetManifest
  }

  interface EvaluationRun {
    assessment_status?: 'meets_policy' | 'below_policy' | 'inconclusive' | null
    legacy_automatic_qualification?: boolean
    decisions?: EvaluationDecisionPayload[]
  }
}
