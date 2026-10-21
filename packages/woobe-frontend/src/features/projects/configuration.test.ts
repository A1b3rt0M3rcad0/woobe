import { expect, it, vi } from 'vitest'
vi.mock('@/lib/api/client', () => ({ del: vi.fn(), get: vi.fn(), patch: vi.fn(), post: vi.fn(), put: vi.fn() }))
import { checkConfigurationDeletion, configurationKeyMetadata, configurationReturnPath, deleteConfiguration, getConfigurationReadiness, grantConfigurationUse, updateConfiguration, type ConfigurationKey, type ConfigurationConsumer, type ConfigurationUsePolicy } from './configuration'
import { del, get, patch, post } from '@/lib/api/client'
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

const key: ConfigurationKey = { id: 'key-a', key: 'API_KEY', kind: 'secret', description: '', value_format: 'token',
  definition_revision: 7, origin: 'manual', material: 'missing', used_by_count: 0, values: {} }
it('sends definition revisions for metadata edits and deletion', async () => {
  await updateConfiguration('p', key, { description: 'Updated', value_format: 'token' })
  expect(patch).toHaveBeenCalledWith('/core/projects/p/configuration/keys/key-a', { description: 'Updated', value_format: 'token', expected_revision: 7 })
  await deleteConfiguration('p', key)
  expect(del).toHaveBeenCalledWith('/core/projects/p/configuration/keys/key-a', { params: { expected_revision: 7 } })
})

it.each([null, {}, { key_id: 'other', can_delete: true },
  { key_id: 'key-a', definition_revision: 7, scope: 'all_environments', can_delete: true, blockers: { retained_resources: true, legacy_binding: false, active_run: false } },
])('rejects incomplete or contradictory deletion checks (%j)', async result => {
  vi.mocked(get).mockResolvedValue(result)
  await expect(checkConfigurationDeletion('p', key, 'staging')).rejects.toThrow('could not be verified')
})

it('finds the exact key across metadata pages and rejects a response for another environment', async () => {
  vi.mocked(get).mockResolvedValueOnce({ environment: 'staging', items: [], permissions: {}, has_next: true })
    .mockResolvedValueOnce({ environment: 'staging', items: [key], permissions: { 'value:write': true }, has_next: false })
  expect((await configurationKeyMetadata('p', key, 'staging')).item).toEqual(key)
  expect(get).toHaveBeenLastCalledWith('/core/projects/p/configuration/keys', { params: { environment: 'staging', search: 'API_KEY', status: 'all', offset: 50, limit: 50 } })
  vi.mocked(get).mockResolvedValue({ environment: 'production', items: [key] })
  await expect(configurationKeyMetadata('p', key, 'staging')).rejects.toThrow('could not be verified')
})

it.each([false, true])('preserves active approvals and never reactivates revoked environments implicitly (%s)', async revoked => {
  const row: ConfigurationConsumer = { consumer_kind: 'provider_credential', consumer_id: 'connection', definition_revision: '1',
    field_path: '/authentication/fields/api_key', destination: 'https://api.deepseek.com', required: true }
  const existing: ConfigurationUsePolicy = { id: 'policy', consumer_kind: row.consumer_kind, consumer_scope: row.consumer_id,
    destination: 'https://api.deepseek.com/', field_paths: ['/previous-field'], environments: ['staging'], revision: 4, revoked }
  await grantConfigurationUse('p', key.id, row, 'draft', existing)
  expect(post).toHaveBeenLastCalledWith('/core/projects/p/configuration/use-policies', {
    key_id: key.id, consumer_kind: row.consumer_kind, consumer_scope: row.consumer_id, destination: row.destination,
    environments: revoked ? ['draft'] : ['staging', 'draft'], field_paths: revoked ? [row.field_path] : ['/previous-field', row.field_path], expected_revision: 4,
  })
})
