// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import { NetworkExecutionPath } from '@/features/network/components/NetworkExecutionPath'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { isSkillOperation, operationLabel, skillActivityLabel, operationEventLabel } from './operations'
import { skillCount, toolCount, type NetworkAgentInvocation } from '@/features/network/components/networkChatExecution'

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
const roots: ReturnType<typeof createRoot>[] = []
afterEach(() => { act(() => roots.splice(0).forEach(root => root.unmount())); document.body.replaceChildren() })
const activation = { tool_name: 'skills_activate', tool_call_id: 's1', success: true, status: 'success', output: { success: true, output: { name: 'inverse-math', version: '1.0.0' } } }

function renderCalls(calls: Parameters<typeof ToolCallsCollapsible>[0]['toolCalls'], variant: 'playground' | 'network') {
  const host = document.createElement('div'); document.body.append(host)
  const root = createRoot(host); roots.push(root)
  act(() => root.render(<ToolCallsCollapsible toolCalls={calls} variant={variant} />))
  return host
}

describe('Skill execution presentation', () => {
  it.each(['playground', 'network'] as const)('renders Skill identity separately in %s', variant => {
    const host = renderCalls([activation], variant)
    expect(host.textContent).toContain('Skill activity (1) · 1 completed')
    expect(host.textContent).not.toContain('Tool calls')
    act(() => host.querySelector('button')!.click())
    expect(host.textContent).toContain('Activate Skill · inverse-math @ 1.0.0')
    expect(host.querySelector('button')!.getAttribute('aria-expanded')).toBe('true')
  })
  it('separates mixed calls and preserves running and failed states', () => {
    const host = renderCalls([activation, { tool_name: 'skills_read_resource', success: false, status: 'error' }, { tool_name: 'http', success: null, status: 'running' }], 'network')
    expect(host.textContent).toContain('Skill activity (2) · 1 completed · 1 failed')
    expect(host.textContent).toContain('Tool calls (1) · 1 running')
  })
  it('recognizes exact operations and tolerates old serialized receipts', () => {
    expect(isSkillOperation({ tool_name: 'skills_activate_customer' })).toBe(false)
    expect(isSkillOperation({ tool_name: 'toString' })).toBe(false)
    expect(operationLabel({ ...activation, output: JSON.stringify(activation.output) })).toContain('inverse-math')
    expect(operationLabel({ tool_name: 'skills_search', output: 'invalid json' })).toBe('Search Skills')
    expect(operationEventLabel('tool_call_completed', { tool_name: 'skills_activate', skill_name: 'invoice-review', skill_version: '1.0.0' })).toBe('Activate Skill · invoice-review @ 1.0.0')
    expect(operationLabel({ tool_name: 'skills_read_resource', input: { path: 'references/math.md' } })).toBe('Read Skill resource · references/math.md')
  })
  it('distinguishes discovery from activation', () => {
    expect(skillActivityLabel({ tool_name: 'skills_search', status: 'calling_tool' })).toBe('Search Skills…')
    expect(skillActivityLabel({ tool_name: 'skills_activate', status: 'processing_tool_result' })).toBe('Processing Skill result…')
    expect(skillActivityLabel({ tool_name: 'http', status: 'calling_tool' })).toBeNull()
  })
  it('identifies Skills in the Network execution path', () => {
    const host = document.createElement('div'); document.body.append(host)
    const renderer = createRoot(host); roots.push(renderer)
    const root = { spanId: 'root', agentName: 'Agent', source: 'draft', version: 'draft', status: 'success', tools: [activation], children: [] } as unknown as NetworkAgentInvocation
    act(() => renderer.render(<NetworkExecutionPath root={root} onSelect={() => {}} />))
    expect(host.textContent).toContain('Skill activity (1)')
    expect(host.textContent).not.toContain('Tool Call')
  })
  it('counts Skills separately throughout nested Network invocations', () => {
    const root = { tools: [activation, { tool_name: 'http' }], children: [{ tools: [{ tool_name: 'skills_search' }], children: [] }] } as unknown as NetworkAgentInvocation
    expect(toolCount(root)).toBe(1)
    expect(skillCount(root)).toBe(2)
  })
})

const resolvedSearch = {
  tool_name: 'skills_resolve', tool_call_id: 'resolve-search',
  input: { action: 'search' }, success: true, status: 'success',
}
const resolvedActivation = {
  ...activation, tool_name: 'skills_resolve', tool_call_id: 'resolve-activate',
  input: { action: 'activate' },
  output: { success: true, output: { action: 'activate', name: 'inverse-math', version: '1.0.0' } },
}

describe('Skill resolution operation presentation', () => {
  it.each(['playground', 'network'] as const)('renders resolver activity in %s', variant => {
    const host = renderCalls([resolvedSearch, resolvedActivation], variant)
    expect(host.textContent).toContain('Skill activity (2)')
    expect(host.textContent).not.toContain('Tool calls')
    act(() => host.querySelector('button')!.click())
    expect(host.textContent).toContain('Search Skills')
    expect(host.textContent).toContain('Activate Skill · inverse-math @ 1.0.0')
  })
  it('distinguishes search, activation and no matching Skill in old and new receipts', () => {
    expect(isSkillOperation(resolvedSearch)).toBe(true)
    expect(operationLabel(resolvedSearch)).toBe('Search Skills')
    expect(operationLabel(resolvedActivation)).toContain('Activate Skill')
    expect(operationLabel({ tool_name: 'skills_resolve', output: JSON.stringify({ output: { action: 'none' } }) })).toBe('No applicable Skill')
    expect(operationLabel({ tool_name: 'skills_resolve', input: { action: 'toString' } })).toBe('Resolve Skill')
    expect(isSkillOperation({ tool_name: 'skills_resolve_customer' })).toBe(false)
    expect(skillActivityLabel({ tool_name: 'skills_resolve', status: 'calling_tool' })).toBe('Resolve Skill…')
    expect(operationEventLabel('tool_call_completed', resolvedActivation)).toContain('Activate Skill')
  })
  it('counts resolver calls as Skill operations throughout the Network', () => {
    const root = { tools: [resolvedSearch, { tool_name: 'http' }], children: [{ tools: [resolvedActivation], children: [] }] } as unknown as NetworkAgentInvocation
    expect(toolCount(root)).toBe(1)
    expect(skillCount(root)).toBe(2)
  })
})
