// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ConfigurationValueEditor } from './ConfigurationValueEditor'
import { clearConfiguration, writeConfiguration, type ConfigurationKey } from '../configuration'

vi.mock('../configuration', () => ({ clearConfiguration: vi.fn(), writeConfiguration: vi.fn() }))

const key: ConfigurationKey = { id: 'key-a', key: 'API_KEY', kind: 'secret', description: 'Provider authentication',
  value_format: 'token', definition_revision: 1, origin: 'manual', material: 'present', used_by_count: 2,
  values: { draft: { configured: true, material: 'present', revision: 3, value_version: 'opaque-version' } } }
let container: HTMLDivElement
let root: Root
const close = vi.fn()
const saved = vi.fn()

async function render(canWrite = true, canClear = true) {
  await act(async () => { root.render(<ConfigurationValueEditor projectId="project-a" item={key} environment="draft" canWrite={canWrite} canClear={canClear} onClose={close} onSaved={saved} />) })
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
})
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks() })

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
