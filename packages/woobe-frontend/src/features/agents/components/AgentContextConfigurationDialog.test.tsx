// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProviderModel, UpdateProviderModelRequest } from '@/features/provider-models/types'
import { AgentContextConfigurationDialog } from './AgentContextConfigurationDialog'

const fixture = vi.hoisted(() => ({
  models: [] as ProviderModel[],
  updateModel: vi.fn(),
  setField: vi.fn(),
  state: {
    runtimeConfig: {} as Record<string, unknown>,
    temperature: 0.7,
    maxOutputTokens: 8192,
    providerModelId: 'primary',
    fallbackProviderModelId: '',
  },
}))

vi.mock('@/features/playground/AgentEditorContext', () => ({
  useAgentEditor: () => ({ state: fixture.state, setField: fixture.setField }),
}))
vi.mock('@/features/provider-models/api', () => ({
  getProviderModels: async () => structuredClone(fixture.models),
  updateProviderModel: fixture.updateModel,
}))
vi.mock('@/features/provider-credentials/api', () => ({
  getCredentials: async () => [{
    id: 'credential-1', project_id: 'project-1', provider: 'custom', name: 'Provider', status: 'active',
  }],
}))

function model(id: string, metadata: Record<string, unknown> = {}): ProviderModel {
  return {
    id, name: id, model: `custom/${id}`, project_id: 'project-1',
    provider_credential_id: 'credential-1', provider: 'custom', status: 'active', metadata,
  }
}

let root: Root
let container: HTMLDivElement
let client: QueryClient

async function settle() {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })
}

async function renderDialog() {
  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <AgentContextConfigurationDialog open projectId="project-1" managerName="Standard" onClose={vi.fn()} />
      </QueryClientProvider>,
    )
  })
  await settle()
}

async function click(label: string) {
  const button = [...document.querySelectorAll('button')].find(
    item => item.getAttribute('aria-label') === label || item.textContent?.trim() === label,
  )
  expect(button, label).toBeTruthy()
  expect(button!.disabled, label).toBe(false)
  await act(async () => button!.click())
  await settle()
}

function input(label: string) {
  const element = document.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)
  expect(element, label).toBeTruthy()
  return element!
}

async function fill(label: string, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input(label), value)
    input(label).dispatchEvent(new Event('input', { bubbles: true }))
  })
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  fixture.models = [model('primary', {
    max_output_tokens: 4096,
    pricing: { input_cost_per_1m_tokens: 0.1, output_cost_per_1m_tokens: 0.2 },
    custom_note: 'preserve',
  })]
  fixture.state.fallbackProviderModelId = ''
  fixture.state.runtimeConfig = { timeout_seconds: 30, context: { budget: { runtime_reserve_units: 1000 } } }
  fixture.setField.mockReset()
  fixture.updateModel.mockReset().mockImplementation(async (id: string, data: UpdateProviderModelRequest) => {
    fixture.models = fixture.models.map(item => item.id === id ? { ...item, ...data } : item)
    return fixture.models.find(item => item.id === id)
  })
})

afterEach(async () => {
  await act(async () => root.unmount())
  client.clear()
  container.remove()
})

describe('Context Budget capacity configuration', () => {
  it('saves missing model capacity and refreshes Auto without changing the Agent policy', async () => {
    await renderDialog()
    expect(document.body.textContent).toContain('Auto has no effective input budget')
    await click('Configure capacity for primary model')
    expect(input('Context Window').value).toBe('')
    expect(input('Maximum output').value).toBe('4096')
    await fill('Context Window', '65536')
    await click('Save changes')

    expect(fixture.updateModel).toHaveBeenCalledWith('primary', expect.objectContaining({
      metadata: expect.objectContaining({
        context_window: 65536, max_output_tokens: 4096, capability_source: 'manual', custom_note: 'preserve',
        pricing: expect.objectContaining({ input_cost_per_1m_tokens: 0.1, output_cost_per_1m_tokens: 0.2 }),
      }),
    }))
    expect(document.body.textContent).toContain('60,440')
    expect(document.body.textContent).not.toContain('Auto has no effective input budget')
    expect(fixture.setField).not.toHaveBeenCalled()
  })

  it('prefills and preserves limits from the original provider payload when saving', async () => {
    fixture.models = [model('primary', {
      context_window: 0,
      provider_model_raw: { top_provider: { context_length: '65536', max_completion_tokens: '4096' } },
    })]
    await renderDialog()
    await click('Configure capacity for primary model')
    expect(input('Context Window').value).toBe('65536')
    expect(input('Maximum output').value).toBe('4096')
    await click('Save changes')
    expect(fixture.models[0].metadata).toMatchObject({ context_window: 65536, max_output_tokens: 4096 })
  })

  it('configures the fallback independently and previews its smaller budget', async () => {
    fixture.models[0].metadata!.context_window = 65536
    fixture.models.push(model('fallback', { max_output_tokens: 4096 }))
    fixture.state.fallbackProviderModelId = 'fallback'
    await renderDialog()
    expect(document.body.textContent).toContain('Context Window is missing for fallback')
    await click('Configure capacity for fallback model')
    await fill('Context Window', '32000')
    await click('Save changes')
    expect(fixture.updateModel.mock.calls[0][0]).toBe('fallback')
    expect(fixture.models[0].metadata!.context_window).toBe(65536)
    expect(document.body.textContent).toContain('26,904')
    expect(document.body.textContent).toContain('The fallback has a smaller effective context capacity')
  })

  it('keeps the editor open and the budget unknown when saving fails', async () => {
    fixture.updateModel.mockRejectedValueOnce(new Error('Save failed'))
    await renderDialog()
    await click('Configure capacity for primary model')
    await fill('Context Window', '65536')
    await click('Save changes')
    expect(input('Context Window').value).toBe('65536')
    expect(fixture.models[0].metadata!.context_window).toBeUndefined()
    expect(document.body.textContent).toContain('Auto has no effective input budget')
  })

  it('lets a fixed budget be applied when model capacity remains unknown', async () => {
    await renderDialog()
    await click('Custom')
    await fill('Context budget units', '16000')
    await click('Apply')
    expect(fixture.setField).toHaveBeenCalledWith('runtimeConfig', {
      timeout_seconds: 30,
      context: { budget: { max_input_units: 16000, runtime_reserve_units: 1000 } },
    })
    expect(fixture.updateModel).not.toHaveBeenCalled()
  })
})
