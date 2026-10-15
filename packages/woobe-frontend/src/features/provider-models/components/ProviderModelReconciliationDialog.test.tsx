// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ProviderModelReconciliationDialog } from './ProviderModelReconciliationDialog'

const api = vi.hoisted(() => ({ preview: vi.fn(), apply: vi.fn() }))
vi.mock('../api', () => ({ previewProviderModels: api.preview, applyProviderModels: api.apply }))

let root: Root
let client: QueryClient
let container: HTMLDivElement
const evidence = { expected_credential_revision: 1, expected_configuration_revision: 'pins', items: [
  { model_id: 'language', label: 'Language', installed_model_id: null, candidate_digest: 'reviewed',
    state: 'new', change_kind: 'new', proposed_spec: { operations: ['language.generate'], source: 'provider', pricing: {} } },
  { model_id: 'unknown', label: 'Unknown', installed_model_id: null, state: 'unsupported/unclassified', change_kind: 'unsupported/unclassified', proposed_spec: null },
] }

async function settle() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) }) }
async function click(text: string) {
  const button = [...document.querySelectorAll('button')].find(item => item.textContent?.trim() === text)!
  expect(button).toBeTruthy()
  await act(async () => button.click())
  await settle()
}

beforeEach(async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  api.preview.mockReset().mockResolvedValue(structuredClone(evidence))
  api.apply.mockReset().mockResolvedValue({ items: [{ model_id: 'language', result: 'created', provider_model_id: 'new-definition' }], adoption: 'Select the new Model on the Draft' })
  container = document.createElement('div'); document.body.appendChild(container)
  root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  await act(async () => root.render(<QueryClientProvider client={client}><ProviderModelReconciliationDialog projectId="project" credentialId="credential" onClose={vi.fn()} /></QueryClientProvider>))
  await settle()
})

afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })

it('requires selection and confirmation before applying the reviewed evidence', async () => {
  expect(api.preview).toHaveBeenCalledTimes(1)
  expect(api.apply).not.toHaveBeenCalled()
  const unknown = document.querySelector<HTMLInputElement>('input[aria-label="Select Unknown"]')!
  expect(unknown.disabled).toBe(true)
  const choice = document.querySelector<HTMLInputElement>('input[aria-label="Select Language"]')!
  await act(async () => choice.click())
  await click('Apply selected')
  expect(api.apply).not.toHaveBeenCalled()
  await click('Confirm selected changes')
  expect(api.apply).toHaveBeenCalledWith(expect.objectContaining({ environment: 'draft' }), evidence, [evidence.items[0]])
  expect(document.body.textContent).toContain('new-definition')
  expect(document.body.textContent).toContain('Select the new Model on the Draft')
})

it('shows a changed-catalog conflict without claiming success', async () => {
  api.apply.mockRejectedValueOnce(new Error('Catalog evidence changed'))
  await act(async () => document.querySelector<HTMLInputElement>('input[aria-label="Select Language"]')!.click())
  await click('Apply selected')
  await click('Confirm selected changes')
  expect(document.body.textContent).toContain('Catalog evidence changed')
  expect(document.body.textContent).not.toContain('new-definition')
})
