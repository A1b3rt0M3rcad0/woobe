// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { ConfigurationReadinessNotice } from './ConfigurationReadinessNotice'
import { ApiError } from '@/lib/api/errors'
const { query, useQuery } = vi.hoisted(() => ({ query: { data: undefined as unknown, isError: false, isFetching: false, error: undefined as unknown, refetch: vi.fn() }, useQuery: vi.fn() }))
vi.mock('@tanstack/react-query', () => ({ useQuery }))
let root: Root, container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks(); Object.assign(query, { data: undefined, isError: false, isFetching: false, error: undefined })
  useQuery.mockReturnValue(query)
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove() })
async function render(environment: 'draft' | 'production' = 'production', versionId = 'release-a', unsaved = false) {
  await act(async () => root.render(<ConfigurationReadinessNotice projectId="project" targetKind="agent" targetId="agent" environment={environment} versionId={versionId} workspaceId="workspace" unsaved={unsaved} />))
}
it('selects exact environment/release and displays bounded missing configuration without values', async () => {
  query.data = { state: 'blocked', missing_key_count: 1, affected_consumer_count: 2, dependencies: [{ key: 'API_KEY', code: 'CONFIG_MISSING', material: 'missing' }] }
  await render()
  expect(useQuery.mock.calls[0][0].queryKey).toEqual(['configuration-readiness', 'project', 'agent', 'agent', 'production', 'release-a'])
  expect(container.textContent).toContain('1 missing keys · 2 affected connections')
  expect(container.querySelector('details')).not.toBeNull()
  expect(container.querySelector('a')?.href).toContain('/workspaces/workspace/projects/project/environments?environment=production')
  await act(async () => container.querySelector('button')!.click())
  expect(query.refetch).toHaveBeenCalledOnce()
})
it('does not turn unreadable or stale status into ready or echo errors', async () => {
  query.data = { state: 'ready', dependencies: [] }; query.isError = true
  query.error = new ApiError('PRIVATE-CANARY', 403)
  await render()
  expect(container.textContent).toContain('requires permission')
  expect(container.textContent).not.toContain('PRIVATE-CANARY')
  expect(container.querySelector('a')).toBeNull()
  query.error = new ApiError('PRIVATE-CANARY', 503)
  await render()
  expect(container.textContent).toContain('unavailable or incomplete')
})
it('hides ready saved state but qualifies unsaved Draft evidence', async () => {
  query.data = { state: 'ready', dependencies: [] }
  await render(); expect(container.textContent).toBe('')
  await render('draft', undefined, true)
  expect(container.textContent).toContain('Saved definition only')
  expect(query.refetch).not.toHaveBeenCalled()
})
