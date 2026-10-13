// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ConfigurationBatchEditor } from './ConfigurationBatchEditor'
import { writeConfigurationBatch, type ConfigurationKey } from '../configuration'
vi.mock('../configuration', () => ({ writeConfigurationBatch: vi.fn() }))
const keys: ConfigurationKey[] = ['FIRST', 'SECOND'].map((key, index) => ({ id: `key-${index}`, key, kind: 'secret', description: '', value_format: 'token', definition_revision: 1, origin: 'manual', material: 'missing', used_by_count: 0, values: { staging: { configured: false, material: 'missing', revision: index, value_version: null } } }))
let container: HTMLDivElement
let root: Root
const close = vi.fn(), saved = vi.fn()
beforeEach(() => {
  vi.resetAllMocks(); Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks() })
async function render() { await act(async () => root.render(<ConfigurationBatchEditor projectId="project" environment="staging" keys={keys} onClose={close} onSaved={saved} />)) }
async function enter(value: string) {
  const input = document.querySelector<HTMLInputElement>('#batch-key-0')!
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })) })
  return input
}
function button(text: string) { return [...document.querySelectorAll('button')].find(item => item.textContent === text)! }
it('submits one explicit environment and clears material after save', async () => {
  vi.mocked(writeConfigurationBatch).mockResolvedValue({}); await render()
  const input = await enter('private-batch-canary'); expect(input.type).toBe('password')
  await act(async () => button('Save entered values').click())
  expect(writeConfigurationBatch).toHaveBeenCalledWith('project', 'staging', keys, { 'key-0': 'private-batch-canary' }, expect.any(String))
  expect(input.value).toBe(''); expect(saved).toHaveBeenCalledOnce(); expect(close).toHaveBeenCalledOnce()
  expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
})
it('confirms discard and removes rejected material without echoing upstream errors', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  vi.mocked(writeConfigurationBatch).mockRejectedValue(new Error('private-batch-canary'))
  await render(); const input = await enter('private-batch-canary')
  await act(async () => button('Cancel').click()); expect(close).not.toHaveBeenCalled()
  await act(async () => button('Save entered values').click())
  expect(input.value).toBe(''); expect(document.body.textContent).not.toContain('private-batch-canary')
  expect(document.querySelector('[role="alert"]')?.textContent).toContain('not confirmed')
  expect(saved).not.toHaveBeenCalled()
})
