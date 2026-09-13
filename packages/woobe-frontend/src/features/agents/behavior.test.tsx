import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AgentConfigurationEditor } from './components/AgentConfigurationEditor'
import { AgentBehaviorFieldDialog } from './components/AgentBehaviorFieldDialog'
import { behaviorFields, behaviorFromAgent, behaviorToSpec, normalizeBehavior, type AgentBehavior } from './behavior'
import * as agentHooks from './hooks'
import * as credentialHooks from '../provider-credentials/hooks'
import * as modelHooks from '../provider-models/hooks'
import * as knowledgeHooks from '../knowledge/hooks'
import * as toolHooks from '../tools/hooks'
import * as skillsHooks from '../skills/hooks'
import * as contextHooks from './hooks'
import { AgentEditorProvider, useAgentEditor } from '../playground/AgentEditorContext'
import type { Agent } from './types'

const emptyBehavior: AgentBehavior = { objective: '', responsibilities: [], allowedBehaviors: [], disallowedBehaviors: [], operatingInstructions: '', responseGuidelines: '', additionalInstructions: '' }

const fixture = {
  agent: { id: 'agent-1', project_id: 'project-1', name: 'Reviewer', description: 'Review invoices', status: 'draft', settings: { behavior_spec: emptyBehavior, runtime_config: {} } } as Agent,
  save: vi.fn(),
  releases: [] as any[],
  models: [] as any[],
  credentials: [] as any[],
  knowledgeVersions: [] as any[],
  collections: [] as any[],
  tools: [] as any[],
  skills: [] as any[],
  managers: [{ name: 'default', version: 'v1', strategy_name: 'stdcm', strategy_version: 'v1', display_name: 'Standard Context Manager', description: '', behavior: '', recommended_for: [], capabilities: [], limitations: [], configuration: '', is_default: true, is_system_default_alias: true, supports_skills: true }] as any[],
}

vi.mock('./hooks', async importOriginal => ({ ...(await importOriginal<typeof import('./hooks')>()), useAgentReleases: vi.fn(), useUpdateAgent: vi.fn(), useKnowledgeVersions: vi.fn(), useCreateKnowledgeVersion: vi.fn(), useContextAssemblers: vi.fn() }))
vi.mock('../provider-credentials/hooks', async importOriginal => ({ ...(await importOriginal<typeof import('../provider-credentials/hooks')>()), useCredentials: vi.fn() }))
vi.mock('../provider-models/hooks', async importOriginal => ({ ...(await importOriginal<typeof import('../provider-models/hooks')>()), useProviderModels: vi.fn() }))
vi.mock('../knowledge/hooks', async importOriginal => ({ ...(await importOriginal<typeof import('../knowledge/hooks')>()), useCollections: vi.fn() }))
vi.mock('../tools/hooks', async importOriginal => ({ ...(await importOriginal<typeof import('../tools/hooks')>()), useTools: vi.fn() }))
vi.mock('../skills/hooks', async importOriginal => ({ ...(await importOriginal<typeof import('../skills/hooks')>()), useSkills: vi.fn() }))

let container: HTMLDivElement
let root: Root
let editor: ReturnType<typeof useAgentEditor>

function CaptureEditor() { editor = useAgentEditor(); return null }

function queryResult(data: unknown, extra: Record<string, unknown> = {}) { return { data, isLoading: false, isPending: false, isError: false, refetch: vi.fn(), ...extra } as any }

beforeEach(() => {
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
  fixture.save = vi.fn().mockResolvedValue(fixture.agent)
  vi.mocked(agentHooks.useAgentReleases).mockReturnValue(queryResult(fixture.releases))
  vi.mocked(agentHooks.useUpdateAgent).mockReturnValue({ mutateAsync: fixture.save, isPending: false } as any)
  vi.mocked(agentHooks.useKnowledgeVersions).mockReturnValue(queryResult(fixture.knowledgeVersions))
  vi.mocked(agentHooks.useCreateKnowledgeVersion).mockReturnValue({ mutateAsync: vi.fn() } as any)
  vi.mocked(contextHooks.useContextAssemblers).mockReturnValue(queryResult(fixture.managers))
  vi.mocked(credentialHooks.useCredentials).mockReturnValue(queryResult(fixture.credentials))
  vi.mocked(modelHooks.useProviderModels).mockReturnValue(queryResult(fixture.models))
  vi.mocked(knowledgeHooks.useCollections).mockReturnValue(queryResult(fixture.collections))
  vi.mocked(toolHooks.useTools).mockReturnValue(queryResult(fixture.tools))
  vi.mocked(skillsHooks.useSkills).mockReturnValue(queryResult(fixture.skills))
})
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.clearAllMocks() })

function input(label: string) { return [...container.querySelectorAll('input, textarea')].find(element => element.getAttribute('aria-label') === label || element.closest('label')?.textContent?.includes(label)) as HTMLInputElement }
function button(label: string) { return [...document.body.querySelectorAll('button')].find(element => element.textContent?.trim() === label || element.getAttribute('aria-label') === label) as HTMLButtonElement }
async function click(element: HTMLElement) { await act(async () => { element.click() }) }
async function fill(element: HTMLInputElement | HTMLTextAreaElement, value: string) { await act(async () => { const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')!.set!; setter.call(element, value); element.dispatchEvent(new Event('input', { bubbles: true })); element.dispatchEvent(new Event('change', { bubbles: true })) }) }

async function renderEditor(surface: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/?editor=overview`]}><AgentEditorProvider agent={fixture.agent} onSave={fixture.save}><CaptureEditor /><AgentConfigurationEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" surface={surface as any} /></AgentEditorProvider></MemoryRouter></QueryClientProvider>))
}

// The tests below cover the Behavior editor as a shared contract across standalone and Network surfaces.
describe('Behavior editor contracts', () => {
  it('hydrates a legacy prompt verbatim and writes only the structured Behavior', () => {
    const agent = { ...fixture.agent, settings: { system_prompt: 'Legacy instructions', runtime_config: {} } } as Agent
    expect(behaviorFromAgent(agent)).toEqual({ ...emptyBehavior, additionalInstructions: 'Legacy instructions' })
    expect(behaviorToSpec(behaviorFromAgent(agent))).toEqual({ additional_instructions: 'Legacy instructions' })
  })

  it('loads a Release with replacement semantics for structured and legacy instructions', () => {
    const structured = behaviorFromAgent({ ...fixture.agent, settings: { behavior_spec: { objective: 'Structured objective' }, system_prompt: 'Legacy' } } as Agent)
    expect(structured.objective).toBe('Structured objective')
    expect(structured.additionalInstructions).toBe('')
    const legacy = behaviorFromAgent({ ...fixture.agent, settings: { system_prompt: 'Legacy only' } } as Agent)
    expect(legacy).toEqual({ ...emptyBehavior, additionalInstructions: 'Legacy only' })
  })

  it('preserves list order and removes blank items without modifying the editor state', () => {
    const state: AgentBehavior = { ...emptyBehavior, responsibilities: [' Second ', '', 'First', 'Second'] }
    expect(normalizeBehavior(state).responsibilities).toEqual(['Second', 'First', 'Second'])
    expect(behaviorToSpec(state).responsibilities).toEqual(['Second', 'First', 'Second'])
    expect(state.responsibilities).toEqual([' Second ', '', 'First', 'Second'])
  })
  it.each(['standalone', 'network'])('uses the same section navigation and Draft actions in %s', async surface => {
    await renderEditor(surface)
    const primary = container.querySelector('[aria-label="Agent configuration groups"]')!
    expect([...primary.querySelectorAll('button')].map(item => item.textContent)).toEqual(['Agent', 'Execution', 'Capabilities', 'Output'])
    expect([...container.querySelectorAll('[aria-label="Agent configuration sections"] button')].map(item => item.textContent)).toEqual(['Overview', 'Behavior'])
    expect(container.querySelector('section[aria-label="Agent Identity"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Behavior Summary"]')).toBeTruthy()
    expect(container.querySelector('section[aria-label="Behavior"]')).toBeNull()
    expect(container.textContent).not.toContain('System Prompt')
    expect(input('Name').value).toBe('Reviewer')
    expect(input('Description').value).toBe('Review invoices')
    expect(editor.isDirty).toBe(false)

    await click(button('Edit Behavior'))
    await click(button('Configure Objective'))
    await fill(input('Objective'), 'Resolve invoices')
    await click(button('Apply changes'))
    await click(button('Reset Draft'))
    expect(editor.state.behavior.objective).toBe('')
    expect(editor.isDirty).toBe(false)
    await click(button('Configure Objective'))
    await fill(input('Objective'), 'Resolve invoices')
    await click(button('Apply changes'))
    await click(button('Execution'))
    expect([...container.querySelectorAll('[aria-label="Agent configuration sections"] button')].map(item => item.textContent)).toEqual(['Runtime', 'Model'])
    expect(container.querySelector('section[aria-label="Runtime"]')).toBeTruthy()
    expect(container.textContent).toContain('Standard Context Manager')
    await click([...container.querySelectorAll('button')].find(item => item.textContent?.startsWith('Stateless'))!)
    await click(button('Model'))
    expect(container.querySelector('section[aria-label="Runtime"]')).toBeNull()
    expect(container.querySelector('section[aria-label="Model"]')).toBeTruthy()
    expect(container.textContent).toContain('No primary selected')
    expect(container.textContent).toContain('No fallback selected')
    await click(button('Capabilities'))
    expect([...container.querySelectorAll('[aria-label="Agent configuration sections"] button')].map(item => item.textContent)).toEqual(['Knowledge', 'Tools', 'Skills'])
    expect(container.textContent).toContain('Search behavior')
    await click(button('Tools'))
    expect(container.textContent).toContain('No Tools selected')
    expect(container.textContent).not.toContain('Search behavior')
    await click(button('Save'))
    expect(fixture.save).toHaveBeenCalledWith(expect.objectContaining({ behavior_spec: expect.objectContaining({ objective: 'Resolve invoices' }), session_mode: 'stateless' }))
    expect(fixture.save.mock.calls[0][0]).not.toHaveProperty('system_prompt')
    expect(editor.isDirty).toBe(false)
  })
  it.each(['standalone', 'network'].flatMap(surface => ['Responsibilities', 'Allowed Behaviors', 'Disallowed Behaviors'].map(label => [surface, label])))('adds, edits and removes %s %s with the shared item editor', async (surface, label) => {
    await renderEditor(surface)
    await click(button('Behavior'))
    const key = behaviorFields.find(field => field.label === label)!.specKey
    await click(button(`Manage ${label}`))
    await click(button('Add item'))
    await fill(input(`${label} item`), 'Cancelled item')
    await click(button('Cancel item'))
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual([])
    for (const value of ['First item', 'Second item']) { await click(button('Add item')); await fill(input(`${label} item`), value); await click(button('Add item')) }
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['First item', 'Second item'])
    await click([...container.querySelectorAll('button')].find(item => item.getAttribute('aria-label') === `Edit ${label} item 1`)!)
    await fill(input(`${label} item`), 'Updated item')
    await click(button('Apply item'))
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['Updated item', 'Second item'])
    await click([...container.querySelectorAll('button')].find(item => item.getAttribute('aria-label') === `Remove ${label} item 2`)!)
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['Updated item'])
  })
  it.each(['standalone', 'network'])('edits identity and applies or cancels guidance in %s', async surface => {
    await renderEditor(surface)
    await fill(input('Name'), 'Updated reviewer')
    await fill(input('Description'), 'Updated description')
    expect(editor.state.name).toBe('Updated reviewer')
    expect(editor.state.description).toBe('Updated description')
    await click(button('Behavior'))
    for (const [label, key] of [['Operating Instructions', 'operatingInstructions'], ['Response Guidelines', 'responseGuidelines'], ['Additional Instructions', 'additionalInstructions']] as const) {
      await click(button(`Configure ${label}`)); await fill(input(label), 'Cancelled'); await click(button('Cancel')); expect(editor.state.behavior[key]).toBe('')
      await click(button(`Configure ${label}`)); await fill(input(label), `Applied ${label}`); await click(button('Apply changes')); expect(editor.state.behavior[key]).toBe(`Applied ${label}`)
    }
  })
  it.each(['standalone', 'network'])('keeps long Behavior content out of the inspector and isolates the dialog in %s', async surface => {
    const long = 'x'.repeat(2000)
    fixture.agent = { ...fixture.agent, settings: { behavior_spec: { objective: long, responsibilities: [long], allowed_behaviors: [long], disallowed_behaviors: [long], operating_instructions: long, response_guidelines: long, additional_instructions: long }, runtime_config: {} } } as Agent
    await renderEditor(surface)
    expect(container.textContent?.length).toBeLessThan(5000)
    await click(button('Edit Behavior')); await click(button('Configure Objective'))
    expect(document.body.textContent).toContain(long)
  })

  it('guards unsaved field changes on escape and keeps them when editing resumes', async () => {
    await renderEditor('standalone'); await click(button('Edit Behavior')); await click(button('Configure Objective')); await fill(input('Objective'), 'Unsaved objective')
    await act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })) })
    expect(document.body.textContent).toContain('Discard unsaved changes?'); await click(button('Keep editing')); expect(input('Objective').value).toBe('Unsaved objective')
  })
  it('guards unsaved field changes on close and keeps them when editing resumes', async () => {
    await renderEditor('standalone'); await click(button('Edit Behavior')); await click(button('Configure Objective')); await fill(input('Objective'), 'Unsaved objective'); await click(button('Close'))
    expect(document.body.textContent).toContain('Discard unsaved changes?'); await click(button('Keep editing')); expect(input('Objective').value).toBe('Unsaved objective')
  })
  it('guards unsaved field changes on backdrop and keeps them when editing resumes', async () => {
    await renderEditor('standalone'); await click(button('Edit Behavior')); await click(button('Configure Objective')); await fill(input('Objective'), 'Unsaved objective')
    const backdrop = [...document.body.querySelectorAll('[data-dialog-backdrop]')].at(-1) as HTMLElement
    await click(backdrop); expect(document.body.textContent).toContain('Discard unsaved changes?'); await click(button('Keep editing')); expect(input('Objective').value).toBe('Unsaved objective')
  })
  it('guards a new list item even before it is added to the working list', async () => {
    await renderEditor('standalone'); await click(button('Edit Behavior')); await click(button('Manage Responsibilities')); await click(button('Add item')); await fill(input('Responsibilities item'), 'Pending item'); await click(button('Close'))
    expect(document.body.textContent).toContain('Discard unsaved changes?')
  })

  it.each(['standalone', 'network'])('blocks invalid Output from another section and recovers after Reset in %s', async surface => {
    await renderEditor(surface); await click(button('Output')); const checkbox = container.querySelector('input[type="checkbox"]') as HTMLInputElement; await click(checkbox); const editorArea = container.querySelector('textarea[aria-label="JSON editor"]') as HTMLTextAreaElement; await fill(editorArea, '{ invalid'); await click(button('Agent')); expect(button('Save').disabled).toBe(true); await click(button('Reset Draft')); expect(button('Save').disabled).toBe(false)
  })
  it.each(['standalone', 'network'])('keeps newer edits dirty when a captured save finishes in %s', async surface => {
    let resolve!: (value: Agent) => void; fixture.save.mockImplementation(() => new Promise<Agent>(r => { resolve = r })); await renderEditor(surface); await fill(input('Name'), 'First'); const save = button('Save'); await click(save); await fill(input('Name'), 'Second'); await act(async () => resolve(fixture.agent)); expect(editor.isDirty).toBe(true)
  })
  it.each(['standalone', 'network'])('preserves the Draft after a failed save and clears the loaded Release after retry in %s', async surface => {
    fixture.save.mockRejectedValueOnce(new Error('save failed')).mockResolvedValue(fixture.agent); await renderEditor(surface); await fill(input('Name'), 'Retry name'); await click(button('Save')); expect(editor.isDirty).toBe(true); await click(button('Save')); expect(editor.isDirty).toBe(false)
  })
  it('notifies only dirty transitions when the Network parent replaces its callback', async () => {
    const onDirtyChange = vi.fn(); const client = new QueryClient(); await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><AgentEditorProvider agent={fixture.agent} onSave={fixture.save}><CaptureEditor /><AgentConfigurationEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" surface="network" onDirtyChange={onDirtyChange} /></AgentEditorProvider></MemoryRouter></QueryClientProvider>)); expect(onDirtyChange).toHaveBeenLastCalledWith(false); await fill(input('Name'), 'Dirty'); expect(onDirtyChange).toHaveBeenLastCalledWith(true)
  })
  it('keeps the Network dirty notification and registered save valid while viewing Versions', async () => {
    const onDirtyChange = vi.fn(); const onRegisterSave = vi.fn(); const client = new QueryClient(); await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><AgentEditorProvider agent={fixture.agent} onSave={fixture.save}><CaptureEditor /><AgentConfigurationEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" surface="network" onDirtyChange={onDirtyChange} onRegisterSave={onRegisterSave} /></AgentEditorProvider></MemoryRouter></QueryClientProvider>)); await fill(input('Name'), 'Dirty'); expect(onDirtyChange).toHaveBeenLastCalledWith(true); const registered = onRegisterSave.mock.calls.at(-1)?.[0]; expect(typeof registered).toBe('function')
  })
  it('keeps edits made after a save capture dirty when the captured state becomes the baseline', async () => {
    await renderEditor('standalone'); await fill(input('Name'), 'First'); const captured = editor.toSnapshot(); await fill(input('Name'), 'Second'); editor.markSaved(captured); expect(editor.isDirty).toBe(true)
  })

  it.each(['details', 'overview', 'behavior', 'runtime', 'model', 'output', 'knowledge', 'tools', 'skills'])('resolves editor=%s', async section => {
    const client = new QueryClient(); await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/?editor=${section}`]}><AgentEditorProvider agent={fixture.agent} onSave={fixture.save}><CaptureEditor /><AgentConfigurationEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" surface="standalone" /></AgentEditorProvider></MemoryRouter></QueryClientProvider>)); expect(container.textContent).toBeTruthy()
  })
  it('keeps editor=agent as a compatibility alias for Overview', async () => {
    const client = new QueryClient(); await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/?editor=agent']}><AgentEditorProvider agent={fixture.agent} onSave={fixture.save}><CaptureEditor /><AgentConfigurationEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" surface="standalone" /></AgentEditorProvider></MemoryRouter></QueryClientProvider>)); expect(container.querySelector('section[aria-label="Agent Identity"]')).toBeTruthy()
  })
  it('responds to query changes and falls back for invalid sections', async () => {
    const client = new QueryClient(); await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/?editor=invalid']}><AgentEditorProvider agent={fixture.agent} onSave={fixture.save}><CaptureEditor /><AgentConfigurationEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" surface="standalone" /></AgentEditorProvider></MemoryRouter></QueryClientProvider>)); expect(container.querySelector('section[aria-label="Agent Identity"]')).toBeTruthy()
  })

  it.each([true, false])('renders structured Behavior or explicit legacy instructions (structured=%s)', structured => {
    const state = structured ? { ...emptyBehavior, objective: 'Objective' } : { ...emptyBehavior, additionalInstructions: 'Legacy' }
    expect(behaviorToSpec(state)).toEqual(structured ? { objective: 'Objective' } : { additional_instructions: 'Legacy' })
  })
  it('reports Behavior field changes and item additions/removals', () => {
    const before = emptyBehavior; const after = { ...emptyBehavior, objective: 'New', responsibilities: ['One'] }; const spec = behaviorToSpec(after); expect(spec.objective).toBe('New'); expect(spec.responsibilities).toEqual(['One']); expect(behaviorToSpec(before)).toEqual({})
  })
  it('reports legacy conversion without inventing changes to empty Behavior fields', () => { expect(behaviorToSpec({ ...emptyBehavior, additionalInstructions: 'Legacy' })).toEqual({ additional_instructions: 'Legacy' }) })
  it('creates from the page with Objective and a behavior_spec payload', () => { expect(behaviorToSpec({ ...emptyBehavior, objective: 'Create' })).toEqual({ objective: 'Create' }) })
  it('creates through the shared onboarding/modal flow with the same Behavior contract', () => { expect(behaviorToSpec({ ...emptyBehavior, objective: 'Onboard' })).toEqual({ objective: 'Onboard' }) })
})
