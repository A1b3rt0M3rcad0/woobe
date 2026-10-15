import { expect, it, vi } from 'vitest'
vi.mock('@/lib/api/client', () => ({ del: vi.fn(), get: vi.fn(), post: vi.fn(), put: vi.fn() }))
import { configurationReturnPath, getConfigurationReadiness } from './configuration'
import { get } from '@/lib/api/client'
it('keeps execution return navigation in the same Project', () => {
  const origin = 'https://woobe.test'
  expect(configurationReturnPath('/projects/p', 'p', origin)).toBe('/projects/p')
  expect(configurationReturnPath('/workspaces/w/projects/p/agents/a/playground?session=s', 'p', origin)).toBe('/workspaces/w/projects/p/agents/a/playground?session=s')
  for (const path of ['//evil.test', '/projects/other/agents/p', '/projects/p/../../outside', '/projects/p/environments', '/projects/p/\\evil', 'javascript:alert(1)']) {
    expect(configurationReturnPath(path, 'p', origin)).toBeNull()
  }
})
it('requests the selected snapshot with a metadata-only GET', async () => {
  vi.mocked(get).mockResolvedValue({ environment: 'production', state: 'ready', required_key_count: 0, missing_key_count: 0, affected_consumer_count: 0, dependencies: [], unresolved: [] })
  await getConfigurationReadiness('p', 'network', 'n', 'production', 'release')
  expect(get).toHaveBeenCalledWith('/core/projects/p/configuration/readiness/network/n', { params: { environment: 'production', version_id: 'release' } })
})

it.each([{}, null, { state: 'ready', dependencies: null }, { state: 'ready', environment: 'draft', dependencies: [] }])('rejects incomplete readiness without crashing the Playground (%j)', async value => {
  vi.mocked(get).mockResolvedValue(value)
  await expect(getConfigurationReadiness('p', 'agent', 'a', 'production')).rejects.toThrow('response is incomplete')
})

it('accepts a partial summary as unknown without promoting page readiness', async () => {
  const { getConfigurationSummary } = await import('./configuration')
  const summary = { environment: 'draft', state: 'unknown', scope: 'current_selections_page', complete: false,
    page_state: 'ready', page_complete: true, has_next: false, checked_at: '2026-06-20T12:00:00Z',
    inspected_target_count: 5, unselected_target_count: 0, affected_target_count: 0,
    blocked_key_count: 0, missing_key_count: 0, required_key_count: 2, affected_consumer_count: 0 }
  vi.mocked(get).mockResolvedValue(summary)
  expect(await getConfigurationSummary('p', 'draft')).toEqual(summary)
  vi.mocked(get).mockResolvedValue({ ...summary, state: 'ready', complete: true })
  await expect(getConfigurationSummary('p', 'draft')).rejects.toThrow('summary is incomplete')
})
