let sequence = 0

/** Build complete v2 events for stream lifecycle fixtures. */
export function runtimeTestEnvelope(type: string, fields: Record<string, unknown>, runKind: 'AGENT' | 'NETWORK' = 'AGENT') {
  const occurred_at = '2026-09-16T20:00:00Z'
  if (type === 'heartbeat' || type === 'run.realtime_unavailable') {
    return { protocol_version: 2, type, occurred_at, payload: fields }
  }
  const assigned = typeof fields.sequence === 'number' ? fields.sequence
    : fields.realtime_available === false ? 0 : ++sequence
  const payload = fields.data && typeof fields.data === 'object' ? fields.data : fields
  return {
    protocol_version: 2, event_id: `event-${assigned}`, sequence: assigned,
    run_id: fields.run_id ?? fields.execution_id ?? 'run-test',
    session_id: fields.session_id ?? fields.network_session_id ?? 'session-test',
    run_kind: runKind, type, occurred_at, payload,
  }
}
