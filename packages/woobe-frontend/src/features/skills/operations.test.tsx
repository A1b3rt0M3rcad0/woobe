// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import { NetworkExecutionPath } from '@/features/network/components/NetworkExecutionPath'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { isSkillOperation, operationLabel, skillActivityLabel, operationEventLabel } from './operations'
import { skillCount, toolCount, type NetworkAgentInvocation } from '@/features/network/components/networkChatExecution'
import { createChatUi, DEFAULT_APPEARANCE } from '../../../../woobe-embed/src/chat-ui'

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

describe('ChatSurface Skill activity', () => {
  it('shows explicit activity even with dots and retains evidence after streaming', () => {
    const host = document.createElement('div'); document.body.append(host)
    const ui = createChatUi(host, DEFAULT_APPEARANCE)
    const message = ui.appendPendingAssistant()
    expect(ui.updateAssistantActivity(message, { tool_name: 'skills_activate', status: 'calling_tool' })).toBe('Activate Skill…')
    ui.updateSkillActivity(message, { ...activation, success: null, status: 'running' })
    ui.updateSkillActivity(message, activation)
    ui.beginAssistantStreaming(message)
    ui.finishAssistantStreaming(message)
    expect(message.querySelectorAll('.skill-activity p')).toHaveLength(1)
    expect(message.textContent).toContain('Activate Skill')
    expect(message.textContent).toContain('completed')
    expect(message.textContent).not.toContain('Tool')
  })
  it('does not leave unfinished Skill activity running after a terminal response', () => {
    const host = document.createElement('div'); document.body.append(host)
    const ui = createChatUi(host, DEFAULT_APPEARANCE)
    const message = ui.appendPendingAssistant()
    ui.updateSkillActivity(message, { tool_name: 'skills_activate', status: 'running' })
    ui.finishAssistantStreaming(message)
    expect(message.textContent).toContain('interrupted')
    expect(message.textContent).not.toContain('running')
  })
  it('renders history evidence and respects generic versus named detail', () => {
    const host = document.createElement('div'); document.body.append(host)
    const ui = createChatUi(host, { ...DEFAULT_APPEARANCE, activity: { ...DEFAULT_APPEARANCE.activity, detail_level: 'generic' } })
    const message = ui.appendMessage('assistant', 'Answer')
    ui.updateSkillActivity(message, activation)
    expect(message.textContent).not.toContain('inverse-math')
    ui.setAppearance({ ...DEFAULT_APPEARANCE, activity: { ...DEFAULT_APPEARANCE.activity, detail_level: 'named' } })
    ui.updateSkillActivity(message, activation)
    expect(message.textContent).toContain('inverse-math @ 1.0.0')
    ui.updateSkillActivity(message, { tool_name: 'skills_read_resource', skill_name: 'invoice-review', skill_version: '2.0.0', success: true })
    expect(message.textContent).toContain('invoice-review @ 2.0.0')
    ui.updateSkillActivity(message, { tool_name: 'http', success: true })
    expect(message.querySelectorAll('.skill-activity p')).toHaveLength(2)
  })
})
