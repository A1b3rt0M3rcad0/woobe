// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ConfigurationKeyDeclarationDialog } from './ConfigurationKeyDeclarationDialog'
import { declareConfiguration, updateConfiguration, type ConfigurationKey } from '../configuration'

vi.mock('../configuration', () => ({ declareConfiguration: vi.fn(), updateConfiguration: vi.fn() }))
const item: ConfigurationKey = { id: 'key-a', key: 'API_KEY', kind: 'secret', description: 'Provider',
  value_format: 'token', definition_revision: 4, origin: 'manual', material: 'missing', used_by_count: 2, values: {} }
const close = vi.fn(), saved = vi.fn(), configure = vi.fn()
let container: HTMLDivElement, root: Root
function button(text: string) { return [...document.querySelectorAll('button')].find(node => node.textContent === text)! }
async function change(selector: string, value: string) {
  const input = document.querySelector<HTMLInputElement | HTMLSelectElement>(selector)!
  await act(async () => {
    Object.getOwnPropertyDescriptor(input instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event(input instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
  })
}
beforeEach(() => {
  vi.resetAllMocks()
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove() })

describe('Configuration declaration and editing', () => {
  it('selects the environment inside the creation modal and opens value configuration there', async () => {
    vi.mocked(declareConfiguration).mockResolvedValue(item)
    await act(async () => root.render(<ConfigurationKeyDeclarationDialog projectId="project-a" environment="draft" onClose={close} onSaved={saved} onConfigure={configure} />))
    await change('#configuration-key', 'API_KEY')
    await change('#configuration-create-environment', 'production')
    await act(async () => button('Create and set value').click())
    expect(declareConfiguration).toHaveBeenCalledWith('project-a', { key: 'API_KEY', kind: 'secret', value_format: 'token', description: '' })
    expect(configure).toHaveBeenCalledWith(expect.objectContaining({ id: 'key-a', values: {} }), 'production')
    expect(saved).toHaveBeenCalledOnce(); expect(close).toHaveBeenCalledOnce()
  })

  it('edits an in-use key without changing its identity or kind', async () => {
    vi.mocked(updateConfiguration).mockResolvedValue(item)
    await act(async () => root.render(<ConfigurationKeyDeclarationDialog projectId="project-a" item={item} onClose={close} onSaved={saved} />))
    expect(document.querySelector<HTMLInputElement>('#configuration-key')!.readOnly).toBe(true)
    expect(document.querySelector<HTMLSelectElement>('#configuration-kind')!.disabled).toBe(true)
    await change('#configuration-description', 'Updated provider')
    await act(async () => button('Save changes').click())
    expect(updateConfiguration).toHaveBeenCalledWith('project-a', item, { description: 'Updated provider', value_format: 'token' })
    expect(declareConfiguration).not.toHaveBeenCalled()
  })

  it('keeps the modal open with a sanitized error when the revision or format is rejected', async () => {
    vi.mocked(updateConfiguration).mockRejectedValue(new Error('private-definition-canary'))
    await act(async () => root.render(<ConfigurationKeyDeclarationDialog projectId="project-a" item={item} onClose={close} onSaved={saved} />))
    await act(async () => button('Save changes').click())
    expect(close).not.toHaveBeenCalled(); expect(saved).not.toHaveBeenCalled()
    expect(document.body.textContent).not.toContain('private-definition-canary')
    expect(document.querySelector('[role=alert]')!.textContent).toContain('not saved')
  })
})
