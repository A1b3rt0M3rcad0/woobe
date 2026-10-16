// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api/errors'
import { ConfigurationUsageDialog } from './ConfigurationUsageDialog'
import { configurationUsage, grantConfigurationUse, revokeConfigurationUse, type ConfigurationConsumer, type ConfigurationKey, type ConfigurationUsePolicy } from '../configuration'
vi.mock('../configuration', () => ({ configurationUsage: vi.fn(), grantConfigurationUse: vi.fn(), revokeConfigurationUse: vi.fn(), configurationKeyByName: vi.fn(), listConfigurationPolicies: vi.fn() }))
const key: ConfigurationKey = { id: 'key', key: 'DEEPSEEK_API_KEY', kind: 'secret', description: '', value_format: 'token', definition_revision: 1,
  origin: 'manual', material: 'present', used_by_count: 1, values: { draft: { configured: true, material: 'present', revision: 1, value_version: 'opaque' } } }
const policy: ConfigurationUsePolicy = { id: 'policy', consumer_kind: 'provider_credential', consumer_scope: 'connection', destination: 'https://api.deepseek.com/',
  environments: ['draft'], field_paths: ['/authentication/fields/api_key'], revision: 1, revoked: false }
let row: ConfigurationConsumer
let root: Root, container: HTMLDivElement, client: QueryClient
const approved = vi.fn()
const button = (name: string) => [...document.querySelectorAll('button')].find(button => button.textContent === name)
const settle = async () => act(async () => { await new Promise(resolve => setTimeout(resolve, 15)) })
beforeEach(() => {
  vi.resetAllMocks(); Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  row = { consumer_kind: 'provider_credential', consumer_id: 'connection', definition_revision: '1', field_path: '/authentication/fields/api_key',
    destination: 'https://api.deepseek.com', required: true, approval: { state: 'approved', policy, update_policy: policy } }
  vi.mocked(configurationUsage).mockImplementation(async () => ({ items: [row], total: 1, offset: 0, limit: 50 }))
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })
async function render(environment: 'draft' | 'staging' = 'draft', canApprove = true) {
  await act(async () => root.render(<QueryClientProvider client={client}><ConfigurationUsageDialog projectId="project" item={key} environment={environment} canApprove={canApprove} onClose={() => {}} onApprovalChange={approved} /></QueryClientProvider>))
  await settle()
}
it('recognizes an existing approval with a canonical trailing slash and does not offer duplicate approval', async () => {
  await render()
  expect(document.body.textContent).toContain('Use approved in Draft')
  expect(button('Approve use in Draft')).toBeUndefined()
  expect(button('Revoke access')).toBeDefined()
  expect(grantConfigurationUse).not.toHaveBeenCalled()
  expect(document.querySelectorAll('[role=dialog]')).toHaveLength(1)
})
it('extends the current canonical policy revision only after an explicit action and refreshes status', async () => {
  row.approval = { state: 'approval_required', policy: null, update_policy: policy }
  vi.mocked(grantConfigurationUse).mockImplementation(async () => {
    row = { ...row, approval: { state: 'approved', policy: { ...policy, environments: ['draft', 'staging'], revision: 2 }, update_policy: policy } }
    return {}
  })
  await render('staging')
  expect(document.body.textContent).toContain('Approval required in Staging')
  expect(grantConfigurationUse).not.toHaveBeenCalled()
  await act(async () => button('Approve use in Staging')!.click()); await settle()
  expect(grantConfigurationUse).toHaveBeenCalledWith('project', 'key', expect.objectContaining({ destination: 'https://api.deepseek.com' }), 'staging', policy)
  expect(document.body.textContent).toContain('Use approved in Staging')
  expect(button('Approve use in Staging')).toBeUndefined()
  expect(approved).toHaveBeenLastCalledWith(true)
  expect(document.body.textContent).not.toContain('Value saved.')
})
it('refreshes a concurrent approval conflict and stops offering an already completed action', async () => {
  row.approval = { state: 'approval_required', policy: null, update_policy: null }
  vi.mocked(grantConfigurationUse).mockImplementation(async () => {
    row = { ...row, approval: { state: 'approved', policy, update_policy: policy } }
    throw new ApiError('private-canary', 409)
  })
  await render()
  await act(async () => button('Approve use in Draft')!.click()); await settle()
  expect(document.body.textContent).toContain('Use approved in Draft')
  expect(document.body.textContent).not.toContain('private-canary')
  expect(document.querySelector('[role=alert]')).toBeNull()
  expect(button('Approve use in Draft')).toBeUndefined()
  expect(approved).toHaveBeenLastCalledWith(true)
})
it('shows access restrictions and requires explicit confirmation for revocation', async () => {
  await render('draft', false)
  expect(button('Revoke access')).toBeUndefined()
  await render()
  await act(async () => button('Revoke access')!.click())
  expect(revokeConfigurationUse).not.toHaveBeenCalled()
  expect(document.querySelectorAll('[role=dialog]')).toHaveLength(1)
  expect(document.body.textContent).toContain('Revoke this approval?')
  vi.mocked(revokeConfigurationUse).mockImplementation(async () => {
    row = { ...row, approval: { state: 'approval_required', policy: null, update_policy: { ...policy, revoked: true, revision: 2 } } }
    return {}
  })
  await act(async () => button('Revoke approval')!.click()); await settle()
  expect(revokeConfigurationUse).toHaveBeenCalledWith('project', policy)
  expect(document.body.textContent).toContain('Approval required in Draft')
  expect(approved).toHaveBeenLastCalledWith(false)
})
