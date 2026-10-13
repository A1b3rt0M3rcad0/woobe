import { expect, it, vi } from 'vitest'
vi.mock('@/lib/api/client', () => ({ del: vi.fn(), get: vi.fn(), post: vi.fn(), put: vi.fn() }))
import { configurationReturnPath, getConfigurationReadiness } from './configuration'
import { get } from '@/lib/api/client'
it('keeps execution return navigation in the same Project', () => {
  const origin = 'https://woobe.test'
  expect(configurationReturnPath('/workspaces/w/projects/p/agents/a/playground?session=s', 'p', origin)).toBe('/workspaces/w/projects/p/agents/a/playground?session=s')
  for (const path of ['//evil.test', '/projects/other/agents/p', '/projects/p/../../outside', '/projects/p/environments', '/projects/p/\\evil', 'javascript:alert(1)']) {
    expect(configurationReturnPath(path, 'p', origin)).toBeNull()
  }
})
it('requests the selected snapshot with a metadata-only GET', () => {
  getConfigurationReadiness('p', 'network', 'n', 'production', 'release')
  expect(get).toHaveBeenCalledWith('/core/projects/p/configuration/readiness/network/n', { params: { environment: 'production', version_id: 'release' } })
})
