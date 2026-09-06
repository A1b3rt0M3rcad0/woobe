/** Presentation of the three reserved Skill runtime operations, including historical Runs. */
export interface OperationInfo {
  tool_name?: string | null
  skill_name?: string | null
  skill_version?: string | null
  input?: unknown
  output?: unknown
}

const actions: Record<string, string> = {
  skills_search: 'Search Skills',
  skills_activate: 'Activate Skill',
  skills_read_resource: 'Read Skill resource',
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value === 'string') {
    try { return record(JSON.parse(value)) } catch { return {} }
  }
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

export function isSkillOperation(call: OperationInfo): boolean {
  return Object.prototype.hasOwnProperty.call(actions, call?.tool_name ?? '')
}

export function operationLabel(call: OperationInfo): string {
  if (!isSkillOperation(call)) return call.tool_name || 'Unknown Tool'
  const input = record(call.input)
  const result = record(call.output)
  const output = record(result.output ?? result)
  const name = typeof call.skill_name === 'string' ? call.skill_name : typeof output.name === 'string' ? output.name : null
  const version = typeof call.skill_version === 'string' ? call.skill_version : typeof output.version === 'string' ? output.version : null
  const path = typeof input.path === 'string' ? input.path : typeof output.path === 'string' ? output.path : null
  const detail = name ? `${name}${version ? ` @ ${version}` : ''}` : null
  return [actions[call.tool_name!], detail, path].filter(Boolean).join(' · ')
}

export function operationGroups<T extends OperationInfo>(calls: T[]) {
  return [
    { kind: 'skill' as const, label: 'Skill activity', calls: calls.filter(isSkillOperation) },
    { kind: 'tool' as const, label: 'Tool calls', calls: calls.filter(call => !isSkillOperation(call)) },
  ].filter(group => group.calls.length)
}

export function operationCountsLabel(calls: OperationInfo[]): string {
  return operationGroups(calls).map(group => `${group.label} (${group.calls.length})`).join(' · ') || 'No operations'
}

export function skillActivityLabel(activity: { tool_name?: string | null; status?: string | null }): string | null {
  if (!isSkillOperation(activity)) return null
  const finished = activity.status === 'processing_tool_result' || activity.status === 'completed'
  if (finished) return 'Processing Skill result…'
  return `${operationLabel(activity)}…`
}

/** Product-facing event title. Raw transport names remain available in technical evidence. */
export function operationEventLabel(eventType: string, payload: unknown): string {
  const data = record(payload)
  const call = { ...data, tool_name: typeof data.tool_name === 'string' ? data.tool_name : null }
  return isSkillOperation(call) ? operationLabel(call) : eventType
}
