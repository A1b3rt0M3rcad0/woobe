// @vitest-environment jsdom
import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Sidebar } from '@/components/layout/Sidebar'
import { AppRouter } from '@/app/router'
import { NetworkAgentEditor } from '@/features/network/components/NetworkAgentEditor'
import { AgentInspector } from '@/features/playground/components/AgentInspector'
import SkillsPage from '@/pages/SkillsPage'
import { getSkillVersion, importSkill, listSkills, listSkillVersions } from './api'
import { savedSkillInstallations } from './installations'
import type { Agent } from '@/features/agents/types'

const fixture = vi.hoisted(() => ({
  agent: { id: 'agent-1', project_id: 'project-1', name: 'Reviewer', provider: 'openai', model: 'test', status: 'active', settings: {} } as Agent,
  setField: vi.fn(),
  agentsError: false,
  managersError: false,
  snapshot: { id: 'version-1', skill_version_id: 'version-1', skill_id: 'skill-1', project_id: 'project-1', name: 'invoice-review', description: 'Review invoices', version: '1.0.0', package_hash: 'hash', required_tools: [], estimated_instruction_units: 100, resource_paths: [], created_at: '2026-09-06', package: { name: 'invoice-review', description: 'Review invoices', instructions: 'Check totals', skill_md: 'Check totals', resources: {}, required_tools: [] } },
  summary: { id: 'skill-1', project_id: 'project-1', name: 'invoice-review', created_at: '2026-09-06', latest_version_id: 'version-1', latest_version: '1.0.0', latest_description: 'Review invoices', latest_required_tools: [], latest_estimated_instruction_units: 100, latest_resource_count: 0, latest_version_created_at: '2026-09-06', version_count: 1 },
}))
vi.mock('./api', () => ({ listSkills: vi.fn(), listSkillVersions: vi.fn(), getSkillVersion: vi.fn(), importSkill: vi.fn() }))
vi.mock('@/components/layout/SidebarUserCard', () => ({ SidebarUserCard: () => null }))
vi.mock('@/layouts/DashboardLayout', () => ({ DashboardLayout: () => <Outlet /> }))
vi.mock('@/features/auth/ProtectedRoute', () => ({ ProtectedRoute: ({ children }: { children: ReactNode }) => children, PublicRoute: ({ children }: { children: ReactNode }) => children }))
vi.mock('@/features/auth/AuthProvider', () => ({ useAuth: () => ({ isAuthenticated: true }) }))
vi.mock('@/pages/AgentPlaygroundPage', () => ({ default: () => <Location /> }))
vi.mock('@/features/workspace/WorkspaceProvider', () => ({ useWorkspace: () => ({
  currentWorkspace: { id: 'workspace-1', name: 'Workspace' }, currentProject: { id: 'project-1', workspace_id: 'workspace-1', name: 'Project' },
  workspaces: [{ id: 'workspace-1' }], projects: [{ id: 'project-1', workspace_id: 'workspace-1' }], isLoadingWorkspaces: false, isLoadingProjects: false,
  selectWorkspace: vi.fn(), selectProject: vi.fn(),
}) }))
vi.mock('@/features/agents/hooks', async original => ({ ...await original<typeof import('@/features/agents/hooks')>(),
  useAgents: () => ({ data: fixture.agentsError ? undefined : [fixture.agent], isPending: false, isSuccess: !fixture.agentsError, isError: fixture.agentsError, error: new Error('Agents unavailable'), refetch: vi.fn() }),
  useContextAssemblers: () => ({ data: fixture.managersError ? [] : [{ name: 'stdcm', version: 'v2', strategy_name: 'stdcm', strategy_version: 'v2', display_name: 'Standard v2', supports_skills: true, recommended_for: [], capabilities: [], limitations: [] }], isPending: false, isError: fixture.managersError, refetch: vi.fn() }),
  useCreateRelease: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateAgent: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('@/features/playground/AgentEditorContext', () => ({ useAgentEditor: () => ({
  state: { name: 'Reviewer', description: '', behavior: { objective: '', responsibilities: [], allowedBehaviors: [], disallowedBehaviors: [], operatingInstructions: '', responseGuidelines: '', additionalInstructions: '' }, sessionMode: 'stateful', runtimeConfig: {} }, setField: fixture.setField,
  loadedReleaseVersion: null, isDirty: false, toSnapshot: () => ({}), updateBaseline: vi.fn(), resetToBaseline: vi.fn(),
}) }))

let container: HTMLDivElement
let root: Root
let client: QueryClient
function Location() { const location = useLocation(); return <output>{location.pathname}{location.search}</output> }
async function render(children: ReactNode, path = '/workspaces/workspace-1/projects/project-1/skills', appRouter = false) {
  await act(async () => { root.render(<QueryClientProvider client={client}>{appRouter ? children : <MemoryRouter initialEntries={[path]}><Routes><Route path="/workspaces/:workspaceId/projects/:projectId/*" element={children} /></Routes></MemoryRouter>}</QueryClientProvider>) })
}
function button(text: string) {
  const matches = [...document.querySelectorAll('button')].filter(element => element.textContent?.trim() === text)
  expect(matches.length, `Button ${text} should be visible once`).toBe(1)
  return matches[0]
}
async function click(element: HTMLElement) { await act(async () => { element.click() }) }
async function settle(assertion: () => void) {
  await vi.waitFor(async () => { await act(async () => { await new Promise(resolve => setTimeout(resolve, 5)) }); assertion() })
}
async function fill(label: string, value: string) {
  const parent = [...document.querySelectorAll('label')].find(element => element.textContent?.trim() === label)
  const input = parent?.querySelector('input, textarea') as HTMLInputElement | HTMLTextAreaElement
  expect(input).toBeTruthy()
  await act(async () => {
    const prototype = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  vi.clearAllMocks(); fixture.agentsError = false; fixture.managersError = false; fixture.agent.settings = {}
  vi.mocked(listSkills).mockResolvedValue([fixture.summary])
  vi.mocked(listSkillVersions).mockResolvedValue([fixture.snapshot])
  vi.mocked(getSkillVersion).mockResolvedValue(fixture.snapshot)
  vi.mocked(importSkill).mockResolvedValue(fixture.snapshot)
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })

describe('Skills navigation regression', () => {
  it('adds an active Skills link alongside other Project artifacts', async () => {
    await render(<Sidebar />)
    const link = [...container.querySelectorAll('a')].find(element => element.textContent === 'Skills')!
    expect(link.getAttribute('href')).toBe('/workspaces/workspace-1/projects/project-1/skills')
    expect(link.getAttribute('aria-current')).toBe('page')
  })
  it.each(['/workspaces/workspace-1/projects/project-1/skills', '/projects/project-1/skills'])('opens the real catalog route %s', async path => {
    window.history.replaceState({}, '', path)
    await render(<AppRouter />, path, true)
    await settle(() => expect(container.querySelector('h1')?.textContent).toBe('Skills'))
    expect(listSkills).toHaveBeenCalledWith('project-1', '', 0)
  })
  it('renders the Project catalog as operational cards and opens Skill details without replacing the page', async () => {
    await render(<SkillsPage />)
    await settle(() => expect(container.textContent).toContain('v1.0.0'))
    expect(container.textContent).toContain('1 version')
    expect(container.textContent).toContain('≈ 100 units')
    const card = [...container.querySelectorAll('button')].find(element => element.getAttribute('aria-label') === 'Open Skill invoice-review')!
    await click(card)
    await settle(() => expect(document.body.textContent).toContain('SHA-256 hash'))
    expect(container.querySelector('h1')?.textContent).toBe('Skills')
  })
  it.each(['standalone', 'network'])('makes Skills visible and usable in the %s editor', async surface => {
    const editor = surface === 'network' ? <NetworkAgentEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" /> : <AgentInspector agent={fixture.agent} projectId="project-1" agentId="agent-1" activeTab="editor" environment="draft" environmentRelease={null} onTabChange={vi.fn()} />
    await render(editor)
    await click(button('Skills'))
    expect(button('Skills').getAttribute('aria-pressed')).toBe('true')
    expect(container.querySelector('section[aria-label="Installed Skills"]')).toBeTruthy()
    expect(button('Manage Skills').disabled).toBe(false)
    await click(button('Manage Skills'))
    await settle(() => expect(document.body.textContent).toContain('invoice-review'))
    expect(button('Create Skill')).toBeTruthy()
  })
  it('opens the requested version from a Project installation link without saving implicitly', async () => {
    await render(<NetworkAgentEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" />, '/workspaces/workspace-1/projects/project-1/agents/agent-1/playground?editor=skills&skill_version_id=version-1')
    await settle(() => expect(document.body.textContent).toContain('SHA-256 hash'))
    expect(button('Skills').getAttribute('aria-pressed')).toBe('true')
    expect(fixture.setField).not.toHaveBeenCalled()
    await click(button('Install on Agent'))
    expect(fixture.setField).toHaveBeenCalledWith('runtimeConfig', expect.objectContaining({ skills: expect.objectContaining({ bindings: [{ skill_id: 'skill-1', skill_version_id: 'version-1', enabled: true }] }) }))
  })
  it('keeps catalog management available when a compatible manager cannot load', async () => {
    fixture.managersError = true
    await render(<NetworkAgentEditor agent={fixture.agent} projectId="project-1" agentId="agent-1" />)
    await click(button('Skills')); await click(button('Manage Skills'))
    await settle(() => expect(button('Create Skill')).toBeTruthy())
    expect(document.body.textContent).toContain('Installation requires a compatible Context Manager')
  })
  it('creates a Skill from named fields and exposes the published version for review', async () => {
    window.history.replaceState({}, '', '/workspaces/workspace-1/projects/project-1/skills')
    await render(<AppRouter />, '', true)
    await click(button('Create Skill'))
    await fill('Name', 'invoice-review'); await fill('When to use this Skill', 'Review invoices'); await fill('Instructions', 'Check totals')
    await click(button('Publish version to catalog'))
    await settle(() => expect(importSkill).toHaveBeenCalledWith('project-1', { version: '1.0.0', skill_md: '---\nname: "invoice-review"\ndescription: "Review invoices"\n---\nCheck totals', resources: {}, required_tools: [] }, undefined))
    await settle(() => expect(document.body.textContent).toContain('SHA-256 hash'))
    await click(button('Install on Agent')); await click(button('Reviewer'))
    await settle(() => expect(container.querySelector('output')?.textContent).toBe('/workspaces/workspace-1/projects/project-1/agents/agent-1/playground?editor=skills&skill_version_id=version-1'))
  })
  it('lists saved installations including disabled versions as operational cards and opens the Agent Skills editor', async () => {
    fixture.agent.settings = { runtime_config: { skills: { bindings: [{ skill_id: 'skill-1', skill_version_id: 'version-1', enabled: false }], snapshots: [fixture.snapshot] } } }
    await render(<><SkillsPage /><Location /></>)
    await click([...container.querySelectorAll('button')].find(element => element.getAttribute('role') === 'tab' && element.textContent?.includes('Installed on Agents'))!)
    expect(container.textContent).toContain('v1.0.0')
    expect(container.textContent).toContain('Disabled')
    const installation = [...container.querySelectorAll('button')].find(element => element.getAttribute('aria-label') === 'Open Agent Skills for Reviewer')!
    await click(installation)
    await settle(() => expect(container.querySelector('output')?.textContent).toContain('/agents/agent-1/playground?editor=skills'))
    expect(savedSkillInstallations([fixture.agent], 'another-project')).toEqual([])
  })
  it('distinguishes an empty catalog from a failed catalog request', async () => {
    vi.mocked(listSkills).mockResolvedValue([])
    await render(<SkillsPage />)
    await settle(() => expect(container.textContent).toContain('No Skills yet'))
    vi.mocked(listSkills).mockRejectedValue(new Error('Catalog unavailable'))
    await act(async () => { await client.invalidateQueries({ queryKey: ['skills'] }) })
    await settle(() => expect(container.textContent).toContain('Catalog unavailable'))
  })
})
