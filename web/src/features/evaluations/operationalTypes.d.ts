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
  evidence_revision: number
  assessment_hash?: string | null
  decision: 'accepted' | 'rejected'
  note?: string | null
  decided_by: string
  decided_at: string
  superseded_at?: string | null
  superseded_reason?: string | null
}

interface EvaluationJudgmentRetry {
  attempt?: number
  status?: string
  started_at?: string
  completed_at?: string | null
  trial_count?: number
  preserved_runtime_evidence?: boolean
  previous_evidence_revision?: number
  evidence_revision?: number
}

declare module './types' {
  interface EvaluationTarget {
    manifest?: EvaluationTargetManifest
  }

  interface EvaluationEstimate {
    assumptions?: Record<string, unknown>
    created_at?: string
  }

  interface EvaluationRun {
    assessment_status?: 'meets_policy' | 'below_policy' | 'inconclusive' | 'pending' | null
    evidence_revision?: number
    judgment_retry?: EvaluationJudgmentRetry | null
    legacy_automatic_qualification?: boolean
    decisions?: EvaluationDecisionPayload[]
  }
}
