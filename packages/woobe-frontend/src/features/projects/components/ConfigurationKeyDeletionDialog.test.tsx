// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ConfigurationKeyDeletionDialog } from './ConfigurationKeyDeletionDialog'
import { checkConfigurationDeletion, deleteConfiguration, type ConfigurationKey, type ConfigurationDeletionCheck } from '../configuration'

vi.mock('../configuration', () => ({ checkConfigurationDeletion: vi.fn(), deleteConfiguration: vi.fn() }))
const item: ConfigurationKey = { id: 'key-a', key: 'API_KEY', kind: 'secret', description: '', value_format: 'token',
  definition_revision: 4, origin: 'manual', material: 'present', used_by_count: 0, values: {} }
const available: ConfigurationDeletionCheck = { key_id: item.id, definition_revision: 4, can_delete: true, scope: 'all_environments',
  blockers: { retained_resources: false, legacy_binding: false, active_run: false } }
const close = vi.fn(), saved = vi.fn()
let container: HTMLDivElement, root: Root, client: QueryClient
function button(text: string) { return [...document.querySelectorAll('button')].find(node => node.textContent === text)! }
async function settle() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) }) }
async function render() {
  await act(async () => root.render(<QueryClientProvider client={client}><ConfigurationKeyDeletionDialog projectId="project-a" item={item} environment="staging" onClose={close} onSaved={saved} /></QueryClientProvider>))
  await settle()
}
beforeEach(() => {
  vi.resetAllMocks(); Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })

describe('Configuration deletion', () => {
  it('checks current usage before enabling explicit deletion', async () => {
    let resolve!: (result: ConfigurationDeletionCheck) => void
    vi.mocked(checkConfigurationDeletion).mockReturnValue(new Promise(done => { resolve = done }))
    vi.mocked(deleteConfiguration).mockResolvedValue({})
    await render()
    expect(button('Delete key').disabled).toBe(true)
    expect(deleteConfiguration).not.toHaveBeenCalled()
    await act(async () => resolve(available)); await settle()
    expect(checkConfigurationDeletion).toHaveBeenCalledWith('project-a', item, 'staging')
    await act(async () => button('Delete key').click())
    expect(deleteConfiguration).toHaveBeenCalledWith('project-a', item)
    expect(close).toHaveBeenCalledOnce(); expect(saved).toHaveBeenCalledOnce()
  })

  it.each(['retained_resources', 'legacy_binding', 'active_run'] as const)('blocks deletion for %s', async blocker => {
    vi.mocked(checkConfigurationDeletion).mockResolvedValue({ ...available, can_delete: false, blockers: { ...available.blockers, [blocker]: true } })
    await render()
    expect(button('Delete key').disabled).toBe(true)
    expect(document.body.textContent).toContain('You can edit it, but cannot delete it')
    expect(deleteConfiguration).not.toHaveBeenCalled()
  })

  it('does not trust a stale revision or a failed usage check', async () => {
    vi.mocked(checkConfigurationDeletion).mockResolvedValue({ ...available, definition_revision: 5 })
    await render()
    expect(button('Delete key').disabled).toBe(true)
    vi.mocked(checkConfigurationDeletion).mockRejectedValue(new Error('private-usage-canary'))
    await act(async () => button('Refresh usage').click()); await settle()
    expect(button('Delete key').disabled).toBe(true)
    expect(document.body.textContent).not.toContain('private-usage-canary')
  })

  it('rechecks usage when a dependency appears after confirmation', async () => {
    vi.mocked(checkConfigurationDeletion).mockResolvedValueOnce(available).mockResolvedValue({ ...available, can_delete: false, blockers: { ...available.blockers, retained_resources: true } })
    vi.mocked(deleteConfiguration).mockRejectedValue(new Error('CONFIG_REFERENCE_IN_USE'))
    await render()
    await act(async () => button('Delete key').click()); await settle()
    expect(button('Delete key').disabled).toBe(true)
    expect(close).not.toHaveBeenCalled(); expect(saved).not.toHaveBeenCalled()
    expect(checkConfigurationDeletion).toHaveBeenCalledTimes(2)
  })
})
