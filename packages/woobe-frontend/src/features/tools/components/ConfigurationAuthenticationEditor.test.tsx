// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { ConfigurationAuthenticationEditor } from './ConfigurationAuthenticationEditor'
vi.mock('@/features/projects/components/ConfigurationReferenceSelector', () => ({
  ConfigurationReferenceSelector: ({ value }: { value: string }) => <input aria-label="Remote key" value={value} readOnly />,
}))
let root: Root, container: HTMLDivElement
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove() })
it('keeps parent and route authentication labels attached to different controls', async () => {
  await act(async () => root.render(<><ConfigurationAuthenticationEditor projectId="project" value={{ type: 'headers', fields: {} }} onChange={() => {}} />
    <ConfigurationAuthenticationEditor projectId="project" value={{ type: 'headers', fields: {} }} onChange={() => {}} /></>))
  const labels = [...container.querySelectorAll('label')].filter(label => ['Authentication', 'Add header name'].includes(label.textContent || ''))
  expect(labels).toHaveLength(4)
  expect(new Set(labels.map(label => label.htmlFor)).size).toBe(4)
  for (const label of labels) expect(document.getElementById(label.htmlFor)).not.toBeNull()
})
it('adds a remote reference using Enter without changing another editor', async () => {
  const first = vi.fn(), second = vi.fn()
  await act(async () => root.render(<><ConfigurationAuthenticationEditor projectId="project" value={{ type: 'headers', fields: {} }} onChange={first} />
    <ConfigurationAuthenticationEditor projectId="project" value={{ type: 'headers', fields: {} }} onChange={second} /></>))
  const input = container.querySelectorAll<HTMLInputElement>('input[placeholder="X-Client-Token"]')[1]
  await act(async () => { input.value = 'X-Route-Token'; input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })) })
  expect(first).not.toHaveBeenCalled()
  expect(second).toHaveBeenCalledWith({ type: 'headers', fields: { 'X-Route-Token': { source: 'project_environment', key: '' } } })
})
