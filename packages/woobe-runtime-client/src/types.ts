export type RuntimeTerminalStatus =
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'timed_out'
  | 'uncertain'

export interface RuntimeSequenceState {
  sequence: number | null
}

export interface ParsedRuntimeFrame {
  eventType: string
  data: Record<string, unknown>
  payload: Record<string, unknown>
  sequence: number | null
}

export interface RuntimeOutputReconciliation {
  output: string
  append: string
  retract: number
  changed: boolean
}
