// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ConfigurationValueEditor } from './ConfigurationValueEditor'
import { clearConfiguration, configurationKeyMetadata, writeConfiguration, type ConfigurationKey } from '../configuration'

vi.mock('../configuration', () => ({ clearConfiguration: vi.fn(), configurationKeyMetadata: vi.fn(), writeConfiguration: vi.fn() }))

const key: ConfigurationKey = { id: 'key-a', key: 'API_KEY', kind: 'secret', description: 'Provider authentication',
  value_format: 'token', definition_revision: 1, origin: 'manual', material: 'present', used_by_count: 2,
  values: { draft: { configured: true, material: 'present', revision: 3, value_version: 'opaque-version' } } }
let container: HTMLDivElement
let root: Root
const close = vi.fn()
const saved = vi.fn()
let client: QueryClient

async function render(canWrite = true, canClear = true) {
  vi.mocked(configurationKeyMetadata).mockResolvedValue({ item: key, permissions: { 'value:write': canWrite, 'value:clear': canClear } })
  await act(async () => { root.render(<QueryClientProvider client={client}><ConfigurationValueEditor projectId="project-a" item={key} environment="draft" onClose={close} onSaved={saved} /></QueryClientProvider>) })
  await settle()
}
async function settle() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) }) }
async function selectEnvironment(environment: string) {
  await act(async () => {
    const select = document.querySelector<HTMLSelectElement>('#configuration-value-environment')!
    select.value = environment
    select.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await settle()
}
function button(text: string) { return [...document.querySelectorAll('button')].find(node => node.textContent === text)! }
async function type(value: string) {
  const input = document.querySelector<HTMLInputElement>('#configuration-value')!
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); vi.restoreAllMocks() })

describe('Configuration value editor', () => {
  it('starts blank, writes only the chosen environment, then clears input', async () => {
    vi.mocked(writeConfiguration).mockResolvedValue({})
    await render()
    const input = document.querySelector<HTMLInputElement>('#configuration-value')!
    expect(input.value).toBe(''); expect(input.type).toBe('password')
    await type('private-editor-canary')
    await act(async () => button('Replace value').click())
    expect(writeConfiguration).toHaveBeenCalledWith('project-a', key, 'draft', 'private-editor-canary')
    expect(input.value).toBe(''); expect(saved).toHaveBeenCalledOnce(); expect(close).toHaveBeenCalledOnce()
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
  })

  it('keeps an unsaved value until discard is confirmed and clears rejected input', async () => {
    vi.mocked(writeConfiguration).mockRejectedValue(new Error('private-editor-canary'))
    await render(); await type('private-editor-canary')
    await act(async () => button('Cancel').click())
    expect(close).not.toHaveBeenCalled()
    expect(document.querySelectorAll('[role=dialog]')).toHaveLength(2)
    await act(async () => [...document.querySelectorAll('[role=dialog]')].pop()!.querySelector<HTMLButtonElement>('[aria-label="Close dialog"]')!.click())
    await act(async () => button('Replace value').click())
    expect(document.querySelector<HTMLInputElement>('#configuration-value')!.value).toBe('')
    expect(document.body.textContent).not.toContain('private-editor-canary')
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('not saved')
  })

  it('requires explicit confirmation to clear and separates write and clear authority', async () => {
    vi.mocked(clearConfiguration).mockResolvedValue({})
    await render(false, true)
    expect(button('Replace value')).toBeUndefined()
    expect(document.querySelector<HTMLInputElement>('#configuration-value')!.disabled).toBe(true)
    await act(async () => button('Clear value').click())
    expect(clearConfiguration).not.toHaveBeenCalled()
    const buttons = [...document.querySelectorAll('button')].filter(node => node.textContent === 'Clear value')
    await act(async () => buttons[buttons.length - 1]!.click())
    expect(clearConfiguration).toHaveBeenCalledWith('project-a', key, 'draft')
    expect(writeConfiguration).not.toHaveBeenCalled()
  })

  it('loads the selected environment revision and permissions instead of using the toolbar context', async () => {
    await render()
    const staging: ConfigurationKey = { ...key, values: { staging: { configured: true, material: 'present', revision: 9, value_version: 'staging-version' } } }
    vi.mocked(configurationKeyMetadata).mockResolvedValue({ item: staging, permissions: { 'value:write': true } })
    await selectEnvironment('staging')
    expect(configurationKeyMetadata).toHaveBeenLastCalledWith('project-a', key, 'staging')
    await type('staging-private-canary')
    await act(async () => button('Replace value').click())
    expect(writeConfiguration).toHaveBeenCalledWith('project-a', staging, 'staging', 'staging-private-canary')
    expect(saved).toHaveBeenCalledWith('staging')
  })

  it('requires discarding unsaved input before switching and never carries a secret into another environment', async () => {
    await render(); await type('draft-private-canary')
    await selectEnvironment('production')
    expect(document.querySelector<HTMLSelectElement>('#configuration-value-environment')!.value).toBe('draft')
    expect(configurationKeyMetadata).not.toHaveBeenCalledWith('project-a', key, 'production')
    vi.mocked(configurationKeyMetadata).mockResolvedValue({ item: { ...key, values: {} }, permissions: { 'value:write': true } })
    await act(async () => button('Switch environment').click())
    await settle()
    expect(document.querySelector<HTMLInputElement>('#configuration-value')!.value).toBe('')
    expect(writeConfiguration).not.toHaveBeenCalled()
    expect(document.querySelector<HTMLSelectElement>('#configuration-value-environment')!.value).toBe('production')
  })

  it('fails closed when another environment is unreadable or read-only', async () => {
    await render()
    vi.mocked(configurationKeyMetadata).mockRejectedValue(new Error('private-upstream-body'))
    await selectEnvironment('staging')
    expect(document.querySelector<HTMLInputElement>('#configuration-value')!.disabled).toBe(true)
    expect(document.body.textContent).not.toContain('private-upstream-body')
    vi.mocked(configurationKeyMetadata).mockResolvedValue({ item: { ...key, values: {} }, permissions: {} })
    await selectEnvironment('production')
    expect(document.querySelector<HTMLInputElement>('#configuration-value')!.disabled).toBe(true)
    expect(button('Save value')).toBeUndefined()
    expect(writeConfiguration).not.toHaveBeenCalled()
  })
})

it('discards local value only after explicit confirmation', async () => {
  await render(); await type('private-discard-canary')
  await act(async () => button('Cancel').click())
  expect(close).not.toHaveBeenCalled()
  await act(async () => button('Discard value').click())
  expect(close).toHaveBeenCalledOnce()
  expect(writeConfiguration).not.toHaveBeenCalled()
  expect(document.querySelector<HTMLInputElement>('#configuration-value')!.value).toBe('')
})
