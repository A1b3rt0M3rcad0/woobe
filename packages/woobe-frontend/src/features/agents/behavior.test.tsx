// @vitest-environment jsdom
import { act, useState, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { behaviorFields, behaviorFromSpec, behaviorToSpec } from './behavior'
import type { Agent, AgentRelease } from './types'
import { AgentEditorNavigation, useAgentEditorSection } from './components/AgentEditorNavigation'
import { AgentEditorProvider, agentToEditorState, canonicalSnapshot, releaseToEditorState, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentInspector } from '@/features/playground/components/AgentInspector'
import { NetworkAgentWorkspace } from '@/features/network/components/NetworkAgentWorkspace'
import { ReleaseDetailsView } from '@/features/playground/components/ReleaseDetailsView'
import { describeReleaseChanges } from '@/features/playground/components/releasePresentation'
import CreateAgentPage from '@/pages/CreateAgentPage'
import { useAgentCreationFlow, type AgentCreationFlowController } from './hooks/useAgentCreationFlow'

const fixture = vi.hoisted(() => ({
  save: vi.fn(), create: vi.fn(), dirty: vi.fn(), registerSave: vi.fn(),
  releases: [] as AgentRelease[],
  tools: [], models: [] as Array<Record<string, unknown>>, credentials: [] as Array<Record<string, unknown>>,
}))
vi.mock('@/features/agents/hooks', async original => ({ ...await original<typeof import('@/features/agents/hooks')>(),
  useReleases: () => ({ data: fixture.releases }),
  useRelease: (_agentId: string, id: string) => ({ data: fixture.releases.find(item => item.id === id) }),
  useCreateRelease: () => ({ mutateAsync: fixture.save, isPending: false }),
  useCreateAgent: () => ({ mutateAsync: fixture.create, isPending: false }),
  useKnowledgeVersions: () => ({ data: [] }),
  useContextManagers: () => ({ data: [{ name: 'stdcm', display_name: 'Standard Context Manager', description: 'General-purpose context assembly.', behavior: '', recommended_for: [], capabilities: [], limitations: [], configuration: '', is_default: true, supports_skills: true }], isLoading: false, isPending: false, isError: false }),
}))
vi.mock('@/features/provider-credentials/hooks', async original => ({ ...await original<typeof import('@/features/provider-credentials/hooks')>(), useCredentials: () => ({ data: fixture.credentials, refetch: vi.fn() }) }))
vi.mock('@/features/provider-models/hooks', async original => ({ ...await original<typeof import('@/features/provider-models/hooks')>(),
  useProviderModels: () => ({ data: fixture.models }),
  useCreateProviderModel: () => ({ mutateAsync: vi.fn() }),
  useAvailableProviderModels: () => ({ data: [] }),
}))
vi.mock('@/features/tools/hooks', async original => ({ ...await original<typeof import('@/features/tools/hooks')>(), useAgentTools: () => ({ data: fixture.tools }), useTools: () => ({ data: fixture.tools }) }))
vi.mock('@/features/knowledge/hooks', async original => ({ ...await original<typeof import('@/features/knowledge/hooks')>(), useCollections: () => ({ data: [] }) }))
vi.mock('@/features/network/components/NetworkAgentChat', () => ({ NetworkAgentChat: () => <Probe /> }))
vi.mock('@/features/network/components/NetworkAgentVersions', () => ({ NetworkAgentVersions: () => null }))
vi.mock('@/components/ui/JsonEditor', () => ({ JsonEditor: ({ value, onChange, disabled }: { value: string; onChange: (value: string) => void; disabled: boolean }) => <textarea aria-label="Output contract" value={value} onChange={event => onChange(event.target.value)} disabled={disabled} /> }))

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
  if (surface === 'network') {
    await render(<NetworkAgentWorkspace agent={value} projectId="project" networkBinding={{ source: 'draft', version: 'draft' }} onOpenComposition={vi.fn()} onDirtyChange={fixture.dirty} onRegisterSaveAction={fixture.registerSave} />)
  } else {
    await render(<AgentEditorProvider agent={value} projectId="project"><Probe /><AgentInspector agent={value} projectId="project" agentId="agent" activeTab="editor" environment="draft" environmentRelease={null} onTabChange={vi.fn()} /></AgentEditorProvider>)
  }
}
function button(label: string) {
  const match = [...document.querySelectorAll('button')].find(item => item.getAttribute('aria-label') === label || item.textContent?.trim() === label)
  expect(match, label).toBeTruthy()
  return match!
}
function input(label: string) {
  const labelled = [...document.querySelectorAll('label')].find(item => item.textContent?.trim() === label)
  const element = labelled?.htmlFor ? document.getElementById(labelled.htmlFor) : [...document.querySelectorAll('input,textarea')].find(item => item.getAttribute('aria-label') === label)
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
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('HTTP requests are disabled in editor tests') }))
  if (!HTMLElement.prototype.scrollIntoView) HTMLElement.prototype.scrollIntoView = vi.fn()
  if (!globalThis.requestAnimationFrame) globalThis.requestAnimationFrame = callback => setTimeout(() => callback(performance.now()), 0) as unknown as number
  if (!globalThis.cancelAnimationFrame) globalThis.cancelAnimationFrame = id => clearTimeout(id)
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  vi.clearAllMocks(); fixture.releases = []; fixture.models = []; fixture.credentials = []
  fixture.save.mockResolvedValue({}); fixture.create.mockResolvedValue(agent)
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); vi.unstubAllGlobals() })

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
  it.each(['standalone', 'network'])('uses the same section navigation and Draft actions in %s', async surface => {
    await renderEditor(surface)
    const primary = container.querySelector('[aria-label="Agent configuration groups"]')!
    expect([...primary.querySelectorAll('button')].map(item => item.textContent)).toEqual(['Agent', 'Execution', 'Capabilities', 'Contracts'])
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
    for (const value of ['First item', 'Second item']) {
      await click(button('Add item'))
      await fill(input(`${label} item`), value)
      await click(button('Add item'))
    }
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual([])
    await click(button(`Edit ${label.toLowerCase()} 2`))
    await fill(input(`${label} item`), 'Second item edited')
    await click(button('Apply item'))
    await click(button(`Remove ${label.toLowerCase()} 1`))
    await click(button('Apply changes'))
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['Second item edited'])
    expect(fixture.save).not.toHaveBeenCalled()
    await click(button(`Manage ${label}`))
    await click(button(`Remove ${label.toLowerCase()} 1`))
    await click(button('Cancel'))
    expect((editor.toSnapshot().behavior_spec as Record<string, unknown>)[key]).toEqual(['Second item edited'])
  })
  it.each(['standalone', 'network'])('edits identity and applies or cancels guidance in %s', async surface => {
    await renderEditor(surface)
    await fill(input('Name'), 'Auditor')
    await fill(input('Description'), 'Invoice specialist')
    await click(button('Behavior'))
    await click(button('Configure Operating Instructions'))
    await fill(input('Operating Instructions'), 'Cancelled instructions')
    await click(button('Cancel'))
    expect(editor.state.behavior.operatingInstructions).toBe('')
    await click(button('Configure Operating Instructions'))
    await fill(input('Operating Instructions'), 'Check totals')
    await click(button('Apply changes'))
    await click(button('Configure Response Guidelines'))
    await fill(input('Response Guidelines'), 'Be concise')
    await click(button('Apply changes'))
    await click(button('Edit Additional Instructions'))
    expect(input('Additional Instructions').value).toBe(agent.system_prompt)
    await fill(input('Additional Instructions'), 'Extra guidance')
    await click(button('Apply changes'))
    expect(editor.toSnapshot()).toMatchObject({ name: 'Auditor', description: 'Invoice specialist', behavior_spec: { operating_instructions: 'Check totals', response_guidelines: 'Be concise', additional_instructions: 'Extra guidance' } })
    expect(container.querySelectorAll('span[title][tabindex="0"]').length).toBe(7)
  })
  it.each(['standalone', 'network'])('keeps long Behavior content out of the inspector and isolates the dialog in %s', async surface => {
    const behavior = { ...behaviorFromSpec(), objective: 'Long objective '.repeat(1000), responsibilities: Array.from({ length: 100 }, (_, index) => `Task ${index}`) }
    await renderEditor(surface, { ...agent, behavior_spec: behaviorToSpec(behavior) })
    await click(button('Behavior'))
    const section = container.querySelector('section[aria-label="Behavior"]')!
    expect(section.querySelectorAll('button')).toHaveLength(7)
    expect(section.querySelector('textarea')).toBeNull()
    expect(section.textContent).toContain('100 configured')
    expect(section.textContent).not.toContain('Task 99')
    await click(button('Manage Responsibilities'))
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Task 99')
    await click(button('Cancel'))
    await click(button('Edit Objective'))
    expect(input('Objective').value).toBe(behavior.objective)
    await fill(input('Objective'), 'Replacement')
    expect(editor.state.behavior.objective).toBe(behavior.objective)
    expect(editor.isDirty).toBe(false)
    await click(button('Apply changes'))
    expect(editor.state.behavior.objective).toBe('Replacement')
    expect(editor.isDirty).toBe(true)
    expect(fixture.save).not.toHaveBeenCalled()
  })
  it.each(['escape', 'close', 'backdrop'])('guards unsaved field changes on %s and keeps them when editing resumes', async method => {
    await renderEditor('standalone')
    await click(button('Behavior'))
    const trigger = button('Edit Additional Instructions')
    await act(async () => trigger.focus())
    await click(trigger)
    await fill(input('Additional Instructions'), 'Changed instructions')
    if (method === 'escape') await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))
    else if (method === 'close') await click(button('Close dialog'))
    else await click(document.querySelector('.dialog-scrollbars')!.parentElement!)
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Discard changes to this field?')
    await click(button('Keep editing'))
    expect(input('Additional Instructions').value).toBe('Changed instructions')
    await click(button('Close dialog'))
    await click(button('Discard changes'))
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(editor.state.behavior.additionalInstructions).toBe(agent.system_prompt)
    expect(document.activeElement).toBe(trigger)
  })
  it('guards a new list item even before it is added to the working list', async () => {
    await renderEditor('network')
    await click(button('Behavior'))
    await click(button('Manage Responsibilities'))
    await click(button('Add item'))
    await fill(input('Responsibilities item'), 'Pending item')
    await click(button('Close dialog'))
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Discard changes to this field?')
    await click(button('Keep editing'))
    expect(input('Responsibilities item').value).toBe('Pending item')
    await click(button('Add item'))
    await click(button('Apply changes'))
    expect(editor.state.behavior.responsibilities).toEqual(['Pending item'])
  })
  it.each(['standalone', 'network'])('builds Output fields visually without requiring JSON in %s', async surface => {
    await renderEditor(surface)
    await click(button('Contracts'))
    await click(container.querySelector('input[type="checkbox"]')!)
    await click(button('Add field'))
    await fill(input('Field 1 name'), 'answer')
    await click(button('Agent'))
    await click(button('Save'))
    expect(fixture.save).toHaveBeenCalledWith(expect.objectContaining({
      output_schema: {
        type: 'object',
        properties: { answer: { type: 'string' } },
        required: [],
        additionalProperties: false,
      },
      response_format: expect.objectContaining({ enabled: true, type: 'json' }),
    }))
    expect(editor.isDirty).toBe(false)
  })
  it.each(['standalone', 'network'])('keeps newer edits dirty when a captured save finishes in %s', async surface => {
    let finish!: (value: unknown) => void
    fixture.save.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await renderEditor(surface)
    await fill(input('Name'), 'Saved name')
    await click(button('Save'))
    await fill(input('Description'), 'Edited while saving')
    await act(async () => { finish({}) })
    expect(fixture.save).toHaveBeenCalledWith(expect.objectContaining({ name: 'Saved name', description: 'Review invoices' }))
    expect(editor.isDirty).toBe(true)
    await click(button('Reset Draft'))
    expect(input('Name').value).toBe('Saved name')
    expect(input('Description').value).toBe('Review invoices')
  })
  it.each(['standalone', 'network'])('preserves the Draft after a failed save and clears the loaded Release after retry in %s', async surface => {
    fixture.save.mockRejectedValueOnce(new Error('Save unavailable'))
    await renderEditor(surface)
    await act(async () => editor.setLoadedRelease('release', '1.0.0'))
    await fill(input('Name'), 'Retry name')
    await click(button('Save'))
    expect(container.textContent).toContain('Save failed')
    expect(editor.isDirty).toBe(true)
    expect(editor.loadedReleaseVersion).toBe('1.0.0')
    await click(button('Save'))
    expect(editor.isDirty).toBe(false)
    expect(editor.loadedReleaseVersion).toBeNull()
  })
  it('notifies only dirty transitions when the Network parent replaces its callback', async () => {
    function Parent() {
      const [dirtyIds, setDirtyIds] = useState(new Set<string>())
      return <><span data-testid="dirty-count">{dirtyIds.size}</span><NetworkAgentWorkspace
        agent={agent} projectId="project" networkBinding={{ source: 'draft', version: 'draft' }}
        onOpenComposition={() => {}}
        onDirtyChange={dirty => {
          fixture.dirty(dirty)
          // Bound the broken feedback cycle so the regression fails without hanging.
          if (fixture.dirty.mock.calls.length >= 10) return
          setDirtyIds(current => {
            const next = new Set(current)
            if (dirty) next.add(agent.id)
            else next.delete(agent.id)
            return next
          })
        }}
      /></>
    }
    await render(<Parent />)
    expect(fixture.dirty.mock.calls).toEqual([[false]])
    await fill(input('Name'), 'Changed draft')
    expect(fixture.dirty.mock.calls).toEqual([[false], [true]])
    expect(container.querySelector('[data-testid="dirty-count"]')?.textContent).toBe('1')
    await click(button('Reset Draft'))
    expect(fixture.dirty.mock.calls).toEqual([[false], [true], [false]])
    expect(container.querySelector('[data-testid="dirty-count"]')?.textContent).toBe('0')
  })
  it('keeps the Network dirty notification and registered save valid while viewing Versions', async () => {
    await renderEditor('network')
    expect(fixture.dirty).toHaveBeenLastCalledWith(false)
    await fill(input('Name'), 'Network draft')
    expect(fixture.dirty).toHaveBeenLastCalledWith(true)
    await click(button('Versions'))
    let result: boolean | undefined
    await act(async () => { result = await fixture.registerSave.mock.calls[fixture.registerSave.mock.calls.length - 1][0]() })
    expect(result).toBe(true)
    expect(fixture.save).toHaveBeenCalledWith(expect.objectContaining({ name: 'Network draft' }))
    expect(fixture.dirty).toHaveBeenLastCalledWith(false)
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