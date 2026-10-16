import { test, expect } from '@playwright/test'
import { installApi, login, project, workspace, respond, now } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'

const providers = [
  ['openai', 'https://api.openai.com/v1'],
  ['anthropic', 'https://api.anthropic.com'],
  ['deepseek', 'https://api.deepseek.com'],
  ['openrouter', 'https://openrouter.ai/api/v1'],
  ['openai_compatible', 'https://compatible.example.test/v1'],
  ['custom', 'https://compatible.example.test/v1'],
] as const

for (const [provider, destination] of providers) test(`${provider} reviews Draft authorization before loading its catalog`, async ({ page }) => {
  await installApi(page)
  await installResources(page)
  const root = `/workspaces/${workspace.id}/projects/${project.id}`
  const key = `${provider.toUpperCase()}_API_KEY`
  const connection = { id: `connection-${provider}`, project_id: project.id, provider, name: provider,
    status: 'active', created_at: now, metadata: { base_url: destination },
    authentication: { type: 'api_key', fields: { api_key: { source: 'project_environment', key } } } }
  const approvals: Record<string, unknown>[] = []
  const declaration = { id: 'provider-key', key, kind: 'secret', value_format: 'token', description: 'Provider key',
    definition_revision: 1, material: 'present', origin: 'manual', used_by_count: 1, values: {} }
  const consumer = { consumer_kind: 'provider_credential', consumer_id: connection.id, definition_revision: '1',
    field_path: '/authentication/fields/api_key', destination, required: true }
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (path === '/ai/credentials') return respond(route, [connection])
    if (path === '/ai/provider-models') {
      if (!url.searchParams.has('available_for_credential_id')) return respond(route, [])
      expect(url.searchParams.get('environment')).toBe('draft')
      if (!approvals.length) return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({
        success: false, message: 'Configuration use is not authorized for this consumer',
        data: { configuration_schema_version: 'project_configuration.v1', diagnostics: [{ code: 'CONFIG_USAGE_NOT_AUTHORIZED', key, environment: 'draft' }] },
        meta: { complete: false },
      }) })
      return respond(route, [{ id: 'catalog-model', label: `${provider} catalog model`, provider, model_type: 'language',
        operations: ['language.generate'], input_modalities: ['text'], output_modalities: ['text'],
        model_spec: { spec_version: 1, provider: provider === 'custom' ? 'openai_compatible' : provider,
          model_id: 'catalog-model', display_name: `${provider} catalog model`, model_type: 'language',
          operations: ['language.generate'], input_modalities: ['text'], output_modalities: ['text'],
          capabilities: {}, limits: {}, pricing: {}, interaction: { mode: 'conversation' }, metadata: {}, source: 'provider' } }])
    }
    const prefix = `/core/projects/${project.id}/configuration/`
    if (path === prefix + 'keys') {
      const environment = url.searchParams.get('environment') || 'draft'
      return respond(route, { items: [declaration], total: 1, offset: 0, limit: 50, has_next: false, environment,
        permissions: { declare: true, 'use-policy:write': environment === 'draft' } })
    }
    if (path === prefix + 'keys/provider-key/usage') return respond(route, { items: [consumer], total: 1, offset: 0, limit: 50 })
    if (path === prefix + 'keys/provider-key/use-policies') {
      return respond(route, { items: approvals.map(item => ({ ...item, id: 'approval', revision: 1, revoked: false })), total: approvals.length })
    }
    if (path === prefix + 'use-policies') {
      if (route.request().method() === 'POST') {
        approvals.push(route.request().postDataJSON())
        return respond(route, { id: 'approval', revision: 1 })
      }
    }
    return route.fallback()
  })
  await login(page)
  await page.goto(root + '/models')
  const open = async () => {
    await page.getByRole('button', { name: 'New Model', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'New model', exact: true })
    await dialog.getByRole('button', { name: 'Provider & model', exact: true }).click()
    return dialog
  }
  const blocked = await open()
  await expect(blocked.getByText('Draft authorization required', { exact: true })).toBeVisible()
  await expect(blocked.getByText(key, { exact: true })).toBeVisible()
  await expect(blocked.getByText('Provider catalog unavailable', { exact: true })).toHaveCount(0)
  const review = blocked.getByRole('link', { name: 'Review Draft authorization' })
  const reviewUrl = new URL((await review.getAttribute('href'))!, page.url())
  expect(reviewUrl.searchParams.get('key')).toBe(key)
  expect(reviewUrl.searchParams.get('returnTo')).toBe(root + '/models')
  expect(approvals).toEqual([])
  await review.click()
  await expect(page.getByLabel('Search keys', { exact: true })).toHaveValue(key)
  await page.getByRole('button', { name: '1 consumers', exact: true }).click()
  await page.getByRole('button', { name: 'Approve for draft', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: 'Approve use in draft?', exact: true })
  await expect(confirmation).toContainText(destination)
  expect(approvals).toEqual([])
  await confirmation.getByRole('button', { name: 'Approve use', exact: true }).click()
  await expect(confirmation).toHaveCount(0)
  expect(approvals).toEqual([{ key_id: declaration.id, consumer_kind: 'provider_credential', consumer_scope: connection.id,
    destination, environments: ['draft'], field_paths: ['/authentication/fields/api_key'], expected_revision: 0 }])
  await page.getByRole('dialog', { name: `Usage · ${key}`, exact: true }).getByRole('button', { name: 'Close dialog', exact: true }).click()
  await page.getByRole('link', { name: 'Return to execution · no automatic Run', exact: true }).click()
  const ready = await open()
  await expect(ready.getByText(`${provider} catalog model`, { exact: true })).toBeVisible()
  await expect(ready.getByText('Draft authorization required', { exact: true })).toHaveCount(0)
})
