// @vitest-environment jsdom
import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { behaviorFields, behaviorFromSpec, behaviorToSpec } from './behavior'
import type { Agent, AgentRelease } from './types'
import { AgentEditorNavigation, useAgentEditorSection } from './components/AgentEditorNavigation'
import { AgentEditorProvider, agentToEditorState, canonicalSnapshot, releaseToEditorState, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentInspector } from '@/features/playground/components/AgentInspector'
import { NetworkAgentEditor } from '@/features/network/components/NetworkAgentEditor'
import { ReleaseDetailsView } from '@/features/playground/components/ReleaseDetailsView'
import { describeReleaseChanges } from '@/features/playground/components/releasePresentation'
import CreateAgentPage from '@/pages/CreateAgentPage'
import { useAgentCreationFlow, type AgentCreationFlowController } from './hooks/useAgentCreationFlow'

const fixture = vi.hoisted(() => ({
  save: vi.fn(), create: vi.fn(),
  releases: [] as AgentRelease[],
  tools: [], models: [] as Array<Record<string, unknown>>, credentials: [] as Array<Record<string, unknown>>,
}))
vi.mock('@/features/agents/hooks', async original => ({ ...await original<typeof import('@/features/agents/hooks')>(),
  useReleases: () => ({ data: fixture.releases }),
  useCreateRelease: () => ({ mutateAsync: fixture.save, isPending: false }),
  useCreateAgent: () => ({ mutateAsync: fixture.create, isPending: false }),
  useKnowledgeVersions: () => ({ data: [] }),
  useContextAssemblers: () => ({ data: [{ name: 'default', version: 'v1', strategy_name: 'stdcm', strategy_version: 'v1', display_name: 'Standard Context Manager', description: 'General-purpose context assembly.', behavior: '', recommended_for: [], capabilities: [], limitations: [], configuration: '', is_default: true, is_system_default_alias: true, supports_skills: true }], isLoading: false, isPending: false, isError: false }),
}))
vi.mock('@/features/provider-credentials/hooks', async original => ({ ...await original<typeof import('@/features/provider-credentials/hooks')>(), useCredentials: () => ({ data: fixture.credentials, refetch: vi.fn() }) }))
vi.mock('@/features/provider-models/hooks', async original => ({ ...await original<typeof import('@/features/provider-models/hooks')>(),
  useProviderModels: () => ({ data: fixture.models }),
  useCreateProviderModel: () => ({ mutateAsync: vi.fn() }),
  useAvailableProviderModels: () => ({ data: [] }),
}))
vi.mock('@/features/tools/hooks', async original => ({ ...await original<typeof import('@/features/tools/hooks')>(), useAgentTools: () => ({ data: fixture.tools }) }))
vi.mock('@/components/ui/JsonEditor', () => ({ JsonEditor: () => null }))

const agent: Agent = { id: 'agent', project_id: 'project', name: 'Reviewer', description: 'Review invoices', provider: 'openai', model: 'test', status: 'active', session_mode: 'stateful', system_prompt: '  original legacy instructions\n' }
const release = (overrides: Partial<AgentRelease> = {}): AgentRelease => ({ id: 'release', project_id: 'project', agent_id: 'agent', version: '1.0.0', status: 'released', name: 'Frozen', provider: 'openai', model: 'test', session_mode: 'stateful', ...overrides })
let root: Root
let container: HTMLDivElement
let client: QueryClient
let editor: ReturnType<typeof useAgentEditor>
let creation: AgentCreationFlowController

function Probe() { editor = useAgentEditor(); return null }
function CreationProbe() { creation = useAgentCreationFlow({ projectId: 'project', onCreated: vi.fn() }); return null }
function Navigation() {
  const [section, setSection] = useAgentEditorSection()
  const navigate = useNavigate()
  return <><AgentEditorNavigation value={section} onChange={setSection} /><button onClick={() => navigate('?editor=runtime')}>Navigate Runtime</button><button onClick={() => navigate('?editor=invalid')}>Invalid query</button></>
}
async function render(content: ReactNode, path = '/workspaces/workspace/projects/project/agents/agent/playground') {
  await act(async () => { root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/workspaces/:workspaceId/projects/:projectId/*" element={content} /></Routes></MemoryRouter></QueryClientProvider>) })
}
async function renderEditor(surface: string, value = agent) {
  const content = surface === 'network' ? <NetworkAgentEditor agent={value} projectId="project" agentId="agent" /> : <AgentInspector agent={value} projectId="project" agentId="agent" activeTab="editor" environment="draft" environmentRelease={null} onTabChange={vi.fn()} />
  await render(<AgentEditorProvider agent={value} projectId="project"><Probe />{content}</AgentEditorProvider>)
}
function button(label: string) {
  const match = [...container.querySelectorAll('button')].find(item => item.getAttribute('aria-label') === label || item.textContent?.trim() === label)
  expect(match, label).toBeTruthy()
  return match!
}
function input(label: string) {
  const labelled = [...container.querySelectorAll('label')].find(item => item.textContent?.trim() === label)
  const element = labelled?.htmlFor ? document.getElementById(labelled.htmlFor) : [...container.querySelectorAll('input,textarea')].find(item => item.getAttribute('aria-label') === label)
  expect(element, label).toBeTruthy()
  return element as HTMLInputElement | HTMLTextAreaElement
}
async function click(element: HTMLElement) { await act(async () => element.click()) }
async function fill(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  await act(async () => {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  if (!HTMLElement.prototype.scrollIntoView) HTMLElement.prototype.scrollIntoView = vi.fn()
  if (!globalThis.requestAnimationFrame) globalThis.requestAnimationFrame = callback => setTimeout(() => callback(performance.now()), 0) as unknown as number
  if (!globalThis.cancelAnimationFrame) globalThis.cancelAnimationFrame = id => clearTimeout(id)
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  vi.clearAllMocks(); fixture.releases = []; fixture.models = []; fixture.credentials = []
  fixture.save.mockResolvedValue({}); fixture.create.mockResolvedValue(agent)
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })

describe('Behavior editor contracts', () => {
  it('hydrates a legacy prompt verbatim and writes only the structured Behavior', () => {
    const state = agentToEditorState(agent)
    expect(state.behavior.additionalInstructions).toBe('  original legacy instructions\n')
    const snapshot = canonicalSnapshot(state)
    expect(snapshot).not.toHaveProperty('system_prompt')
    expect(snapshot.behavior_spec).toEqual(behaviorToSpec(behaviorFromSpec(null, agent.system_prompt)))
  })
  it('loads a Release with replacement semantics for structured and legacy instructions', () => {
    const current = agentToEditorState({ ...agent, behavior_spec: behaviorToSpec({ ...behaviorFromSpec(), objective: 'Current' }) })
    const legacy = releaseToEditorState(release({ system_prompt: 'Historical' }), current)
    expect(legacy.behavior.objective).toBe('')
    expect(legacy.behavior.additionalInstructions).toBe('Historical')
    const structured = releaseToEditorState(release({ behavior_spec: behaviorToSpec({ ...behaviorFromSpec(), objective: 'Pinned' }), system_prompt: 'Compiled' }), current)
    expect(structured.behavior.objective).toBe('Pinned')
    expect(structured.behavior.additionalInstructions).toBe('')
  })
  it('preserves list order and removes blank items without modifying the editor state', () => {
    const state = behaviorFromSpec()
    state.responsibilities = [' Second ', '', 'First', 'Second']
    expect(behaviorToSpec(state).responsibilities).toEqual(['Second', 'First', 'Second'])
    expect(state.responsibilities).toEqual([' Second ', '', 'First', 'Second'])
  })
  it('renders the standalone editor as four continuous configuration surfaces', async () => {
    await renderEditor('standalone')
    const primary = container.querySelector('[aria-label="Agent configuration groups"]')!
    expect([...primary.querySelectorAll('button')].map(item => item.textContent)).toEqual(['Agent', 'Execution', 'Capabilities', 'Output'])
    expect(container.querySelector('[aria-label="Agent configuration sections"]')).toBeNull()
    expect(container.textContent).not.toContain('System Prompt')
    expect(container.querySelector('section[aria-label="Agent Identity"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Behavior"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Behavior Summary"]')).toBeNull()
    expect(input('Name').value).toBe('Reviewer')
    expect(input('Description').value).toBe('Review invoices')
    expect(editor.isDirty).toBe(false)

    await fill(input('Objective'), 'Resolve invoices')
    expect(editor.isDirty).toBe(true)
    await act(async () => editor.resetToBaseline())
    expect(input('Objective').value).toBe('')
    expect(editor.isDirty).toBe(false)
    await fill(input('Objective'), 'Resolve invoices')

    await click(button('Execution'))
    expect(container.querySelector('section[aria-label="Runtime"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Model"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Context Manager"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Session Mode"]')).toBeTruthy()
    expect(container.textContent).toContain('Standard Context Manager')
    await click([...container.querySelectorAll('button')].find(item => item.textContent?.startsWith('Stateless'))!)
    expect(container.textContent).toContain('does not preserve Agent Session history')
    await click(button('Save draft'))
    expect(fixture.save).toHaveBeenCalledWith(expect.objectContaining({ behavior_spec: expect.objectContaining({ objective: 'Resolve invoices' }), session_mode: 'stateless' }))
    expect(fixture.save.mock.calls[0][0]).not.toHaveProperty('system_prompt')
    expect(editor.isDirty).toBe(false)
  })
  it('keeps the Network editor on its existing secondary-navigation contract', async () => {
    await renderEditor('network')
    const primary = container.querySelector('[aria-label="Agent configuration groups"]')!
    expect([...primary.querySelectorAll('button')].map(item => item.textContent)).toEqual(['Agent', 'Execution', 'Capabilities', 'Output'])
    expect([...container.querySelectorAll('[aria-label="Agent configuration sections"] button')].map(item => item.textContent)).toEqual(['Overview', 'Behavior'])
    expect(container.querySelector('section[aria-label="Agent Identity"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Behavior Summary"]')).toBeTruthy()
    await click(button('Edit Behavior'))
    await fill(input('Objective'), 'Resolve invoices')
    await click(button('Execution'))
    await click(button('Runtime'))
    expect(container.querySelector('section[aria-label="Runtime"]')).toBeTruthy()
    await click([...container.querySelectorAll('button')].find(item => item.textContent?.startsWith('Stateless'))!)
    await click(button('Save'))
    expect(fixture.save).toHaveBeenCalledWith(expect.objectContaining({ behavior_spec: expect.objectContaining({ objective: 'Resolve invoices' }), session_mode: 'stateless' }))
  })
  it.each(['Responsibilities', 'Allowed Behaviors', 'Disallowed Behaviors'])('adds, edits and removes direct standalone %s rows without a second confirmation', async label => {
    await renderEditor('standalone')
    const labels = ['Responsibilities', 'Allowed Behaviors', 'Disallowed Behaviors']
    const addIndex = labels.indexOf(label)

    let addButtons = [...container.querySelectorAll('button')].filter(item => item.textContent?.trim() === 'Add')
    await click(addButtons[addIndex])
    await fill(input(`${label} 1`), 'First item')
    addButtons = [...container.querySelectorAll('button')].filter(item => item.textContent?.trim() === 'Add')
    await click(addButtons[addIndex])
    await fill(input(`${label} 2`), 'Second item')

    expect(container.textContent).not.toContain('Confirm add')
    const key = behaviorFields.find(field => field.label === label)!.specKey
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['First item', 'Second item'])
    await fill(input(`${label} 2`), 'Second item edited')
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['First item', 'Second item edited'])
    await click(button(`Remove ${label.toLowerCase()} 1`))
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['Second item edited'])
  })
  it('edits standalone identity and guidance directly in the central Draft state', async () => {
    await renderEditor('standalone')
    await fill(input('Name'), 'Auditor')
    await fill(input('Description'), 'Invoice specialist')

    await click(button('Configure Operating Instructions'))
    await fill(input('Operating Instructions'), 'Check totals')
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>).operating_instructions).toBe('Check totals')
    await click(button('Close Operating Instructions'))

    await click(button('Configure Response Guidelines'))
    await fill(input('Response Guidelines'), 'Be concise')
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>).response_guidelines).toBe('Be concise')
    await click(button('Close Response Guidelines'))

    const advanced = [...container.querySelectorAll('summary')].find(item => item.textContent?.trim() === 'Advanced instructions')!
    await click(advanced)
    await click(button('Edit Additional Instructions'))
    expect(input('Additional Instructions').value).toBe(agent.system_prompt)
    await fill(input('Additional Instructions'), 'Extra guidance')

    expect(editor.toSnapshot()).toMatchObject({ name: 'Auditor', description: 'Invoice specialist', behavior_spec: { operating_instructions: 'Check totals', response_guidelines: 'Be concise', additional_instructions: 'Extra guidance' } })
    expect(container.querySelectorAll('span[title][tabindex="0"]').length).toBe(7)
    expect(container.textContent).not.toContain('Apply Operating Instructions')
  })
  it('keeps edits made after a save capture dirty when the captured state becomes the baseline', async () => {
    await render(<AgentEditorProvider agent={agent} projectId="project"><Probe /></AgentEditorProvider>)
    await act(async () => editor.setField('name', 'Saved name'))
    const confirmed = editor.state
    await act(async () => editor.setField('description', 'Changed while saving'))
    await act(async () => editor.updateBaseline(confirmed))
    expect(editor.state.name).toBe('Saved name')
    expect(editor.state.description).toBe('Changed while saving')
    expect(editor.isDirty).toBe(true)
    await act(async () => editor.resetToBaseline())
    expect(editor.state.description).toBe('Review invoices')
  })
})

describe('Editor navigation and immutable views', () => {
  it.each([
    ['details', 'Overview'],
    ['overview', 'Overview'],
    ['behavior', 'Behavior'],
    ['runtime', 'Runtime'],
    ['model', 'Model'],
    ['output', 'Output'],
    ['knowledge', 'Knowledge'],
    ['tools', 'Tools'],
    ['skills', 'Skills'],
  ])('resolves editor=%s', async (section, expectedLabel) => {
    await render(<Navigation />, `/workspaces/w/projects/p/agents/a?editor=${section}`)
    const pressed = [...container.querySelectorAll('button[aria-pressed="true"]')].map(item => item.textContent?.trim())
    expect(pressed).toContain(expectedLabel)
  })
  it('keeps editor=agent as a compatibility alias for Overview', async () => {
    await render(<Navigation />, '/workspaces/w/projects/p/agents/a?editor=agent')
    expect(button('Agent').getAttribute('aria-pressed')).toBe('true')
    expect(button('Overview').getAttribute('aria-pressed')).toBe('true')
  })
  it('responds to query changes and falls back for invalid sections', async () => {
    await render(<Navigation />)
    await click(button('Navigate Runtime'))
    expect(button('Execution').getAttribute('aria-pressed')).toBe('true')
    expect(button('Runtime').getAttribute('aria-pressed')).toBe('true')
    await click(button('Invalid query'))
    expect(button('Agent').getAttribute('aria-pressed')).toBe('true')
    expect(button('Overview').getAttribute('aria-pressed')).toBe('true')
  })
  it.each([true, false])('renders structured Behavior or explicit legacy instructions (structured=%s)', async structured => {
    const item = release({ description: 'Frozen role', behavior_spec: structured ? behaviorToSpec({ ...behaviorFromSpec(), objective: 'Frozen objective', responsibilities: ['Check totals'] }) : null, system_prompt: 'Historical instructions' })
    await render(<ReleaseDetailsView release={item} />)
    expect(container.textContent).toContain('Agent Details')
    expect(container.textContent).toContain('Frozen role')
    expect(container.textContent).toContain('Runtime')
    expect(container.textContent).toContain('Context Manager')
    expect(container.textContent).toContain(structured ? 'Frozen objective' : 'Legacy Agent Instructions')
    expect(container.textContent).toContain(structured ? 'Check totals' : 'Historical instructions')
    if (structured) expect(container.textContent).not.toContain('Historical instructions')
  })
  it('reports Behavior field changes and item additions/removals', () => {
    const before = release({ behavior_spec: behaviorToSpec({ ...behaviorFromSpec(), objective: 'Old', responsibilities: ['A'] }) })
    const after = release({ behavior_spec: behaviorToSpec({ ...behaviorFromSpec(), objective: 'New', responsibilities: ['B'] }) })
    expect(describeReleaseChanges(before, after)).toEqual(['Objective was updated', 'Responsibilities: added “B”', 'Responsibilities: removed “A”'])
  })
  it('reports legacy conversion without inventing changes to empty Behavior fields', () => {
    const before = release({ system_prompt: '  Historical instructions\n' })
    const after = release({ behavior_spec: behaviorToSpec(behaviorFromSpec(null, before.system_prompt)) })
    expect(describeReleaseChanges(before, after)).toEqual(['Behavior was structured from legacy instructions'])
    expect(describeReleaseChanges(after, before)).toEqual(['Behavior reverted to legacy instructions'])
  })
})

describe('Agent creation', () => {
  it('creates from the page with Objective and a behavior_spec payload', async () => {
    fixture.credentials = [{ id: 'credential', provider: 'openai', name: 'Primary', status: 'active', metadata: {} }]
    await render(<CreateAgentPage />)
    expect(container.textContent).not.toContain('System Prompt')
    await fill(container.querySelector('input[name="name"]')!, 'Created Agent')
    await fill(input('Objective'), 'Answer accurately')
    await act(async () => {
      const select = container.querySelector('select')!
      select.value = 'credential'; select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    await act(async () => container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
    expect(fixture.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'Created Agent', behavior_spec: expect.objectContaining({ objective: 'Answer accurately', schema_version: 1 }) }))
    expect(fixture.create.mock.calls[0][0]).not.toHaveProperty('system_prompt')
  })
  it('creates through the shared onboarding/modal flow with the same Behavior contract', async () => {
    fixture.credentials = [{ id: 'credential', provider: 'openai', name: 'Primary', status: 'active' }]
    fixture.models = [{ id: 'model', provider_credential_id: 'credential', provider: 'openai', name: 'Model', model: 'test', status: 'active', metadata: {} }]
    await render(<CreationProbe />)
    await act(async () => { creation.setAgentName('Created'); creation.setAgentObjective('Resolve requests'); creation.selectExistingModel('model') })
    await act(async () => { await creation.createAgent() })
    expect(fixture.create).toHaveBeenCalledWith(expect.objectContaining({ behavior_spec: expect.objectContaining({ objective: 'Resolve requests' }) }))
    expect(fixture.create.mock.calls[0][0]).not.toHaveProperty('system_prompt')
  })
})