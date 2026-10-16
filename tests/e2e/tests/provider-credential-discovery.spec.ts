import { test, expect } from '@playwright/test'
import { installApi, login, project, workspace, respond, now } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'

const providers = [
  ['openai', 'https://api.openai.com/v1'], ['anthropic', 'https://api.anthropic.com'],
  ['deepseek', 'https://api.deepseek.com'], ['openrouter', 'https://openrouter.ai/api/v1'],
  ['openai_compatible', 'https://compatible.example.test/v1'], ['custom', 'https://compatible.example.test/v1'],
] as const

const cases = [...providers.map(([provider, destination]) => ({ provider, destination, existing: false, width: 1440 })),
  { provider: 'deepseek', destination: 'https://api.deepseek.com', existing: true, width: 1440 },
  { provider: 'deepseek', destination: 'https://api.deepseek.com', existing: false, width: 390 }]
for (const { provider, destination, existing, width } of cases) test(`${provider} approves use inline and recognizes existing canonical approvals (${existing ? 'already approved' : 'new approval'}, ${width}px)`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  await installApi(page); await installResources(page)
  const root = `/workspaces/${workspace.id}/projects/${project.id}`, key = `${provider.toUpperCase()}_API_KEY`
  const connection = { id: `connection-${provider}`, project_id: project.id, provider, name: provider,
    status: 'active', created_at: now, metadata: { base_url: destination },
    authentication: { type: 'api_key', fields: { api_key: { source: 'project_environment', key } } } }
  const approvals: Record<string, any>[] = []
  let policy: Record<string, any> | null = null, discoveryRequests = 0
  const canonical = new URL(destination).href.replace(/\/+$/, '') + (new URL(destination).pathname === '/' ? '/' : '')
  if (existing) policy = { id: 'approval', consumer_kind: 'provider_credential', consumer_scope: connection.id, destination: canonical, environments: ['draft'], field_paths: ['/authentication/fields/api_key'], revision: 1, revoked: false }
  const approved = (environment: string) => !!policy && policy.environments.includes(environment)
  const consumer = { consumer_kind: 'provider_credential', consumer_id: connection.id, definition_revision: '1',
    field_path: '/authentication/fields/api_key', destination, required: true }
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (path === '/ai/credentials') return respond(route, [connection])
    if (path === '/ai/provider-models') {
      if (!url.searchParams.has('available_for_credential_id')) return respond(route, [])
      discoveryRequests++
      expect(url.searchParams.get('environment')).toBe('draft')
      if (!approved('draft') || (existing && discoveryRequests === 1)) return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({
        success: false, message: 'Configuration use is not authorized for this consumer',
        data: { configuration_schema_version: 'project_configuration.v1', diagnostics: [{ code: 'CONFIG_USAGE_NOT_AUTHORIZED', key, environment: 'draft' }] }, meta: { complete: false },
      }) })
      return respond(route, [{ id: 'catalog-model', label: `${provider} catalog model`, provider, model_type: 'language',
        operations: ['language.generate'], input_modalities: ['text'], output_modalities: ['text'],
        model_spec: { spec_version: 1, provider: provider === 'custom' ? 'openai_compatible' : provider,
          model_id: 'catalog-model', display_name: `${provider} catalog model`, model_type: 'language',
          operations: ['language.generate'], input_modalities: ['text'], output_modalities: ['text'],
          capabilities: {}, limits: {}, pricing: {}, interaction: { mode: 'conversation' }, metadata: {}, source: 'provider' } }])
    }
    const prefix = `/core/projects/${project.id}/configuration/`
    const environment = url.searchParams.get('environment') || 'draft'
    if (path === prefix + 'keys') return respond(route, { items: [{ id: 'provider-key', key, kind: 'secret', value_format: 'token',
      description: 'Provider key', definition_revision: 1, material: 'present', origin: 'manual', used_by_count: 1,
      values: { [environment]: { configured: true, material: 'present', revision: 1, value_version: 'opaque' } },
      approval: { state: approved(environment) ? 'approved' : 'approval_required', connection_count: 1, approved_connection_count: approved(environment) ? 1 : 0 } }],
      total: 1, offset: 0, limit: 50, has_next: false, environment, permissions: { declare: true, 'use-policy:write': environment !== 'production' } })
    if (path === prefix + 'keys/provider-key/usage') return respond(route, { items: [{ ...consumer,
      approval: { state: approved(environment) ? 'approved' : 'approval_required', policy: approved(environment) ? policy : null, update_policy: policy } }], total: 1, offset: 0, limit: 50, environment })
    if (path === prefix + 'keys/provider-key/use-policies') return respond(route, { items: policy ? [policy] : [], total: policy ? 1 : 0 })
    if (path === prefix + 'use-policies' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      if (body.expected_revision !== (policy?.revision ?? 0)) return respond(route, null, 409)
      approvals.push(body)
      policy = { ...body, id: 'approval', destination: canonical, revision: (policy?.revision ?? 0) + 1, revoked: false }
      return respond(route, policy)
    }
    return route.fallback()
  })
  await login(page); await page.goto(root + '/models')
  await page.getByRole('button', { name: 'New Model', exact: true }).click()
  const model = page.getByRole('dialog', { name: 'New model', exact: true })
  await model.getByRole('button', { name: 'Provider & model', exact: true }).click()
  await expect(model.getByText('Draft authorization required', { exact: true })).toBeVisible()
  await model.getByRole('button', { name: 'Approve use in Draft', exact: true }).click()
  const access = page.getByRole('dialog', { name: `Access approvals · ${key}`, exact: true })
  await expect(access).toContainText(destination)
  expect(approvals).toEqual([])
  const beforeApproval = discoveryRequests
  if (!existing) await access.getByRole('button', { name: 'Approve use in Draft', exact: true }).click()
  await expect(access.getByText('Use approved in Draft', { exact: true })).toBeVisible()
  await expect(access.getByRole('button', { name: 'Approve use in Draft', exact: true })).toHaveCount(0)
  expect(discoveryRequests).toBe(beforeApproval)
  if (!existing) expect(approvals[0]).toMatchObject({ key_id: 'provider-key', consumer_kind: 'provider_credential', consumer_scope: connection.id,
    destination, environments: ['draft'], field_paths: ['/authentication/fields/api_key'], expected_revision: 0 })
  await access.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(model.getByText('Use approved in Draft', { exact: true })).toBeVisible()
  await model.getByRole('button', { name: 'Load catalog', exact: true }).click()
  await expect(model.getByText(`${provider} catalog model`, { exact: true })).toBeVisible()
  await page.goto(root + '/environments')
  const row = page.getByRole('row').filter({ has: page.getByRole('region', { name: `Key ${key}`, exact: true }) })
  await expect(row.getByRole('cell', { name: 'Draft status: Value saved', exact: true })).toContainText('Use approved')
  await row.getByRole('button', { name: 'Manage approvals', exact: true }).click()
  await expect(access.getByText('Use approved in Draft', { exact: true })).toBeVisible()
  await expect(access.getByRole('button', { name: 'Approve use in Draft', exact: true })).toHaveCount(0)
  expect(approvals).toHaveLength(existing ? 0 : 1)
  await access.getByLabel('Environment', { exact: true }).selectOption('staging')
  await expect(access.getByText('Approval required in Staging', { exact: true })).toBeVisible()
  await access.getByRole('button', { name: 'Approve use in Staging', exact: true }).click()
  await expect(access.getByText('Use approved in Staging', { exact: true })).toBeVisible()
  expect(approvals[existing ? 0 : 1]).toMatchObject({ expected_revision: 1, environments: ['draft', 'staging'] })
  await access.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(row.getByRole('cell', { name: 'Staging status: Value saved', exact: true })).toContainText('Use approved')
})
