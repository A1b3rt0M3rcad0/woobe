// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useEnvironmentSelection, useSelectedAgentEnvironment, environmentSelectionKey } from './environmentSelection'
import { RuntimeEnvironmentPill } from '@/components/common/RuntimeEnvironmentPill'
import { EnvironmentSelectionNotice } from './EnvironmentSelectionNotice'

const fixture = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/lib/api/client', () => ({ get: fixture.get }))
let root: Root, container: HTMLDivElement, client: QueryClient
let observed: ReturnType<typeof useSelectedAgentEnvironment>
const current = (snapshot: string | null = 'selected', environment = 'production', resource = 'agent', kind = 'Agent') => ({
  resource_id: resource, kind, environment, snapshot_id: snapshot, environment_generation: 2,
  selection_authority: 'asac', remote_status: 'verified', complete: true,
})
const release = (id = 'selected', agent = 'agent', project = 'project') => ({
  id, agent_id: agent, project_id: project, version: '1.2.0', status: 'released', snapshot_kind: 'release',
  provider: 'custom', model: 'immutable-model', session_mode: 'stateless', external_context_contract: { fields: [{ name: 'tenant' }] },
})
function Probe({ project = 'project', agent = 'agent', enabled = true, runtime = true }: { project?: string; agent?: string; enabled?: boolean; runtime?: boolean }) {
  observed = useSelectedAgentEnvironment(project, agent, 'production', enabled)
  return <><RuntimeEnvironmentPill environment="production" available={observed.state === 'selected'} enabled={runtime}
    loading={observed.state === 'loading'} unknown={observed.state === 'unknown'} />
    {observed.snapshot ? <p>{observed.snapshot.model} · {observed.snapshot.session_mode}</p> : <EnvironmentSelectionNotice selection={observed} environment="Production" />}</>
}
async function settle() { for (let i = 0; i < 4; i++) await act(async () => { await new Promise(resolve => setTimeout(resolve, 5)) }) }
async function render(props = {}) { await act(async () => root.render(<QueryClientProvider client={client}><Probe {...props} /></QueryClientProvider>)); await settle() }
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true }); vi.clearAllMocks()
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  fixture.get.mockImplementation(async (path: string, options?: { params?: { environment: string } }) => path.endsWith('/current') ? current('selected', options?.params?.environment) : release())
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })
describe('authoritative environment selection', () => {
  it('uses a released snapshot absent from the catalog and fetches exact immutable details', async () => {
    await render(); expect(container.textContent).toContain('Production Live'); expect(container.textContent).toContain('immutable-model · stateless')
    expect(observed.snapshot?.external_context_contract).toEqual({ fields: [{ name: 'tenant' }] })
    expect(fixture.get).toHaveBeenCalledWith('/ai/agents/agent/releases/selected')
    expect(fixture.get.mock.calls.some(([path]) => path.endsWith('/releases'))).toBe(false)
  })
  it('separates runtime Off from selection', async () => { await render({ runtime: false }); expect(container.textContent).toContain('Production Off'); expect(observed.snapshotId).toBe('selected') })
  it('shows empty only after a complete verified null selection', async () => {
    fixture.get.mockResolvedValue(current(null)); await render(); expect(container.textContent).toContain('No Production'); expect(container.textContent).toContain('then deploy'); expect(fixture.get).toHaveBeenCalledTimes(1)
  })
  it.each([401, 403, 500, 'timeout'])('keeps failed reads unknown (%s)', async (status) => {
    fixture.get.mockRejectedValue(new Error(String(status))); await render(); expect(container.textContent).toContain('Production Unknown'); expect(container.textContent).not.toContain('No Production'); expect(container.querySelector('button')?.textContent).toBe('Retry')
  })
  it('does not claim absence during the initial read', async () => { fixture.get.mockReturnValue(new Promise(() => {})); await render(); expect(container.textContent).toContain('Production…'); expect(container.textContent).not.toContain('No Production') })
  it('keeps verified selection visible when details are forbidden', async () => {
    let forbidden = true
    fixture.get.mockImplementation(async (path: string) => { if (path.endsWith('/current')) return current(); if (forbidden) throw new Error('403'); return release() })
    await render(); expect(container.textContent).toContain('Production Live'); expect(container.textContent).toContain('details unavailable'); expect(observed.snapshot).toBeNull(); expect(observed.state).toBe('selected')
    forbidden = false; await act(async () => container.querySelector('button')!.click()); await settle()
    expect(observed.snapshot?.model).toBe('immutable-model'); expect(observed.detailState).toBe('ready')
  })
  it('does not use cached evidence after a failed refresh', async () => {
    await render(); fixture.get.mockRejectedValue(new Error('offline')); await act(async () => { await observed.refetch() }); await settle()
    expect(observed.state).toBe('unknown'); expect(observed.snapshot).toBeNull(); expect(container.textContent).toContain('Unknown')
    fixture.get.mockImplementation(async (path: string) => path.endsWith('/current') ? current() : release())
    await act(async () => container.querySelector('button')!.click()); await settle()
    expect(observed.state).toBe('selected'); expect(observed.snapshot?.id).toBe('selected')
  })
  it.each(['asac', 'legacy'])('supports %s authority without status inference', async (authority) => {
    fixture.get.mockImplementation(async (path: string) => path.endsWith('/current') ? { ...current(), selection_authority: authority } : release()); await render(); expect(observed.state).toBe('selected'); expect(observed.data?.selection_authority).toBe(authority)
  })
  it('rejects partial or incorrectly scoped observations', async () => {
    fixture.get.mockResolvedValue({ ...current(), complete: false }); await render(); expect(observed.state).toBe('unknown')
    fixture.get.mockResolvedValue(current('selected', 'staging')); await act(async () => { await observed.refetch() }); await settle(); expect(observed.state).toBe('unknown')
  })
  it('rejects foreign details while retaining verified selection', async () => {
    fixture.get.mockImplementation(async (path: string) => path.endsWith('/current') ? current() : release('other', 'other', 'foreign')); await render(); expect(observed.state).toBe('selected'); expect(observed.snapshot).toBeNull(); expect(observed.detailState).toBe('unknown')
  })
  it('observes external deployment A → B → A through refresh', async () => {
    let selected = 'A'; fixture.get.mockImplementation(async (path: string) => path.endsWith('/current') ? current(selected) : release(path.substring(path.lastIndexOf('/') + 1)))
    await render(); expect(observed.snapshot?.id).toBe('A')
    for (const next of ['B', 'A']) { selected = next; await act(async () => { await observed.refetch() }); await settle(); expect(observed.snapshot?.id).toBe(next) }
  })
  it('isolates late responses from a different project/resource', async () => {
    let resolve!: (value: unknown) => void
    fixture.get.mockImplementation(async (path: string) => path.includes('/projects/project/') ? new Promise(done => { resolve = done }) : path.endsWith('/current') ? current('B', 'production', 'second') : release('B', 'second', 'other'))
    await render(); await render({ project: 'other', agent: 'second' }); expect(observed.snapshot?.id).toBe('B')
    await act(async () => resolve(current())); await settle(); expect(observed.snapshot?.id).toBe('B')
  })
  it('deduplicates exact snapshot shared by Staging and Production', async () => {
    function Both() { useSelectedAgentEnvironment('project', 'agent', 'staging'); useSelectedAgentEnvironment('project', 'agent', 'production'); return null }
    await act(async () => root.render(<QueryClientProvider client={client}><Both /></QueryClientProvider>)); await settle(); expect(fixture.get.mock.calls.filter(([path]) => path.endsWith('/releases/selected'))).toHaveLength(1)
  })
  it('separates Network selection from standalone Agent selection', async () => {
    function Both() { useEnvironmentSelection('project', 'Network', 'agent', 'production'); useEnvironmentSelection('project', 'Agent', 'agent', 'production'); return null }
    fixture.get.mockImplementation(async (path: string) => current(path.includes('/networks/') ? 'pinned-network' : 'standalone', 'production', 'agent', path.includes('/networks/') ? 'Network' : 'Agent'))
    await act(async () => root.render(<QueryClientProvider client={client}><Both /></QueryClientProvider>)); await settle()
    expect(client.getQueryData(environmentSelectionKey('project', 'Network', 'agent', 'production'))).toMatchObject({ snapshot_id: 'pinned-network' })
    expect(client.getQueryData(environmentSelectionKey('project', 'Agent', 'agent', 'production'))).toMatchObject({ snapshot_id: 'standalone' })
  })
  it('does not read disabled selections', async () => { await render({ enabled: false }); expect(fixture.get).not.toHaveBeenCalled() })
})
