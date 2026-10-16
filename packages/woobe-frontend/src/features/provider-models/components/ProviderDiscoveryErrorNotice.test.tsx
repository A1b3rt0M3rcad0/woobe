// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api/errors'
import { ProviderDiscoveryErrorNotice, discoveryConfigurationIssue } from './ProviderDiscoveryErrorNotice'

vi.mock('@/lib/api/client', () => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))

let root: Root, container: HTMLDivElement
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove() })
const configurationError = (code: string, key = 'DEEPSEEK_API_KEY', environment = 'draft') => new ApiError('private-upstream-canary', 403, {
  configuration_schema_version: 'project_configuration.v1', diagnostics: [{ code, key, environment }],
})
async function render(error: unknown) {
  const retry = vi.fn(), manual = vi.fn()
  await act(async () => root.render(<MemoryRouter initialEntries={['/workspaces/workspace/projects/project/models']}><Routes>
    <Route path="/workspaces/:workspaceId/projects/:projectId/models" element={<ProviderDiscoveryErrorNotice projectId="project" error={error} onRetry={retry} onManual={manual} />} />
  </Routes></MemoryRouter>))
  return { retry, manual }
}
it('shows the exact configuration blocker and directs approval to Draft without granting it', async () => {
  const { retry, manual } = await render(configurationError('CONFIG_USAGE_NOT_AUTHORIZED'))
  expect(container.textContent).toContain('Draft authorization required')
  expect(container.textContent).toContain('DEEPSEEK_API_KEY')
  expect(container.textContent).not.toContain('Provider catalog unavailable')
  expect(container.textContent).not.toContain('private-upstream-canary')
  const url = new URL(container.querySelector('a')!.href)
  expect(url.pathname).toBe('/workspaces/workspace/projects/project/environments')
  expect(url.searchParams.get('environment')).toBe('draft')
  expect(url.searchParams.get('key')).toBe('DEEPSEEK_API_KEY')
  expect(container.textContent).not.toContain('Enter model ID manually')
  await act(async () => container.querySelector('button')!.click())
  expect(retry).toHaveBeenCalledOnce(); expect(manual).not.toHaveBeenCalled()
})
it('distinguishes missing values and destination approvals from a provider outage', async () => {
  await render(configurationError('CONFIG_VALUE_MISSING'))
  expect(container.textContent).toContain('Draft configuration value required')
  await render(configurationError('CONFIG_DESTINATION_CHANGED'))
  expect(container.textContent).toContain('Draft destination approval required')
  await render(new ApiError('private-upstream-canary', 502))
  expect(container.textContent).toContain('Provider catalog unavailable')
  expect(container.querySelector('a')).toBeNull()
  expect(container.textContent).not.toContain('private-upstream-canary')
})
it('does not trust malformed keys, unrelated errors, or diagnostics for another environment', () => {
  expect(discoveryConfigurationIssue(configurationError('CONFIG_USAGE_NOT_AUTHORIZED', 'private-value / canary'))?.key).toBeNull()
  expect(discoveryConfigurationIssue(configurationError('CONFIG_USAGE_NOT_AUTHORIZED', 'TOKEN', 'production'))).toBeNull()
  expect(discoveryConfigurationIssue(new Error('CONFIG_USAGE_NOT_AUTHORIZED'))).toBeNull()
  expect(discoveryConfigurationIssue(configurationError('toString'))).toBeNull()
})
