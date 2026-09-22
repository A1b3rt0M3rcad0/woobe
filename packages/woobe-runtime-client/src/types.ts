export type RuntimeTerminalStatus =
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'timed_out'
  | 'uncertain'

export interface RuntimeSequenceState {
  sequence: number | null
}

interface RuntimeFrameBase {
  type: string
  eventType: string
  payload: Record<string, unknown>
  occurredAt: string
}

export interface WoobeEvent extends RuntimeFrameBase {
  kind: 'semantic'
  eventId: string
  runId: string
  sessionId: string
  runKind: 'AGENT' | 'NETWORK'
  sequence: number
}

export interface RuntimeControlFrame extends RuntimeFrameBase {
  kind: 'transport'
  sequence: null
}

export type ParsedRuntimeFrame = WoobeEvent | RuntimeControlFrame

export interface RuntimeAssistantMessage {
  message_id: string
  content: string
  output_mode: 'intermediate'
  phase: string | null
  provider: string | null
  model: string | null
  partial: boolean | null
  status: string | null
  completed_at: string | null
}

export interface RuntimeOutputReconciliation {
  output: string
  append: string
  retract: number
  changed: boolean
}
