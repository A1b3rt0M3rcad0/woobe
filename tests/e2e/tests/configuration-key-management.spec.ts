import { test, expect, type Page } from '@playwright/test'
import { installApi, login, project, workspace, respond } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'
import type { ConfigurationKey } from '../../../packages/woobe-frontend/src/features/projects/configuration'
import type { ProjectEnvironment } from '../../../packages/woobe-frontend/src/features/projects/types'

const root = `/workspaces/${workspace.id}/projects/${project.id}/environments`
const empty = { configured: false, material: 'missing' as const, revision: 0, value_version: null }
const key = (id: string, name: string, count = 0): ConfigurationKey => ({
  id, key: name, kind: 'secret', description: 'Synthetic configuration', value_format: 'token', definition_revision: 1,
  origin: 'manual', material: 'missing', used_by_count: count, values: { draft: { ...empty }, staging: { ...empty }, production: { ...empty } },
})

async function setup(page: Page, options: { race?: boolean; keys?: ConfigurationKey[]; environment?: ProjectEnvironment; denied?: ProjectEnvironment[]; readOnly?: ProjectEnvironment[] } = {}) {
  await installApi(page); await installResources(page)
  const keys = options.keys ?? [key('used', 'USED_KEY', 1), key('unused', 'UNUSED_KEY')]
  const writes: { environment: string; revision: number; value: string }[] = []
  const events: string[] = []
  await page.route('**/core/projects/project-a/configuration/**', async route => {
    const url = new URL(route.request().url()), method = route.request().method()
    const suffix = url.pathname.split('/configuration/')[1]
    if (suffix === 'keys' && method === 'GET') {
      const environment = (url.searchParams.get('environment') ?? 'draft') as 'draft' | 'staging' | 'production'
      if (options.denied?.includes(environment)) return respond(route, null, 403)
      const search = url.searchParams.get('search') ?? ''
      const items = keys.filter(item => item.key.includes(search)).map(item => ({ ...item,
        material: item.values[environment]!.material, values: { [environment]: item.values[environment] } }))
      return respond(route, { items, total: items.length, offset: 0, limit: 50, has_next: false, environment,
        permissions: { declare: true, 'value:write': !options.readOnly?.includes(environment), 'value:clear': !options.readOnly?.includes(environment) } })
    }
    if (suffix === 'keys' && method === 'POST') {
      const body = route.request().postDataJSON()
      const created = { ...key('created', body.key), ...body }
      keys.push(created)
      return respond(route, created)
    }
    const parts = suffix.split('/'), item = keys.find(candidate => candidate.id === parts[1])
    if (!item) return respond(route, null, 404)
    if (parts[2] === 'deletion-check') {
      events.push('check')
      const inUse = item.used_by_count > 0
      const response = { key_id: item.id, definition_revision: item.definition_revision, scope: 'all_environments', can_delete: !inUse,
        blockers: { retained_resources: inUse, legacy_binding: false, active_run: false } }
      if (options.race) item.used_by_count = 1
      return respond(route, response)
    }
    if (method === 'DELETE' && parts.length === 2) {
      events.push('delete')
      if (item.used_by_count) return respond(route, null, 409)
      keys.splice(keys.indexOf(item), 1)
      return respond(route, null)
    }
    if (method === 'PATCH') {
      const body = route.request().postDataJSON()
      if (body.expected_revision !== item.definition_revision) return respond(route, null, 409)
      item.description = body.description; item.value_format = body.value_format; item.definition_revision++
      return respond(route, item)
    }
    if (parts[2] === 'values' && method === 'PUT') {
      const environment = parts[3] as 'draft' | 'staging' | 'production'
      const body = route.request().postDataJSON()
      if (body.expected_revision !== item.values[environment]!.revision) return respond(route, null, 409)
      writes.push({ environment, revision: body.expected_revision, value: body.value })
      item.values[environment] = { configured: true, material: 'present', revision: body.expected_revision + 1, value_version: 'opaque-version' }
      return respond(route, {})
    }
    return respond(route, null, 404)
  })
  await login(page)
  await page.goto(options.environment ? `${root}?environment=${options.environment}` : root)
  await expect(page.getByRole('button', { name: 'Add key', exact: true })).toBeVisible()
  return { keys, writes, events }
}

for (const width of [1440, 390]) test(`creates and edits the chosen environment inside the modal at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  const state = await setup(page)
  await page.getByRole('button', { name: 'Add key', exact: true }).click()
  const declaration = page.getByRole('dialog', { name: 'Declare configuration key' })
  await declaration.getByLabel('Key', { exact: true }).fill('NEW_KEY')
  await declaration.getByLabel('Environment for the value').selectOption('staging')
  await declaration.getByRole('button', { name: 'Create and set value' }).click()
  const editor = page.getByRole('dialog', { name: 'Set value · staging' })
  await expect(editor.getByLabel('Environment', { exact: true })).toHaveValue('staging')
  await expect(page.locator('#configuration-environment')).toHaveCount(0)
  await editor.getByLabel('New secret value').fill('synthetic-staging-only')
  await editor.getByRole('button', { name: 'Save value', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('#configuration-environment')).toHaveCount(0)
  const row = page.getByRole('row').filter({ has: page.getByText('NEW_KEY', { exact: true }) })
  await expect(row.getByRole('cell', { name: /^Draft status:/ })).toHaveText('Not set')
  await expect(row.getByRole('cell', { name: /^Staging status:/ })).toHaveText('Value saved')
  expect(state.writes).toEqual([{ environment: 'staging', revision: 0, value: 'synthetic-staging-only' }])
  expect(state.keys.find(item => item.key === 'NEW_KEY')!.values.production!.configured).toBe(false)
})

test('keeps used keys editable and checks usage before deleting an unused key', async ({ page }) => {
  const state = await setup(page)
  const used = page.getByRole('row').filter({ has: page.getByRole('button', { name: 'Delete USED_KEY', exact: true }) })
  await expect(used.getByRole('button', { name: 'Delete USED_KEY', exact: true })).toBeDisabled()
  await used.getByRole('button', { name: 'Edit key', exact: true }).click()
  const editor = page.getByRole('dialog', { name: 'Edit key · USED_KEY' })
  await editor.getByLabel('Description').fill('Updated while in use')
  await editor.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(state.keys.find(item => item.id === 'used')!.description).toBe('Updated while in use')
  await page.getByRole('button', { name: 'Delete UNUSED_KEY', exact: true }).click()
  const deletion = page.getByRole('dialog', { name: 'Delete key · UNUSED_KEY' })
  await expect(deletion.getByRole('button', { name: 'Delete key', exact: true })).toBeEnabled()
  expect(state.events).toEqual(['check'])
  await deletion.getByRole('button', { name: 'Delete key', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(state.events).toEqual(['check', 'delete'])
  expect(state.keys.some(item => item.id === 'unused')).toBe(false)
})

test('blocks deletion when a dependency appears after the initial check', async ({ page }) => {
  const state = await setup(page, { race: true })
  await page.getByRole('button', { name: 'Delete UNUSED_KEY', exact: true }).click()
  const deletion = page.getByRole('dialog', { name: 'Delete key · UNUSED_KEY' })
  await expect(deletion.getByRole('button', { name: 'Delete key', exact: true })).toBeEnabled()
  await deletion.getByRole('button', { name: 'Delete key', exact: true }).click()
  await expect(deletion.getByText('This key is in use. You can edit it, but cannot delete it.')).toBeVisible()
  await expect(deletion.getByRole('button', { name: 'Delete key', exact: true })).toBeDisabled()
  expect(state.keys.some(item => item.id === 'unused')).toBe(true)
})

const formats: { format: ConfigurationKey['value_format']; value: string }[] = [
  { format: 'token', value: `synthetic-token-${'x'.repeat(512)}` },
  { format: 'url', value: `https://example.test/${'long-path/'.repeat(25)}?source=lipo` },
  { format: 'json', value: '{\n  "enabled": true,\n  "nested": { "labels": ["first", "second"] }\n}\n' },
  { format: 'pem', value: `-----BEGIN CERTIFICATE-----\n${'A'.repeat(64)}\n${'B'.repeat(64)}\n-----END CERTIFICATE-----\n` },
  { format: 'string', value: '  First line\nSecond line with trailing spaces  \n' },
]

for (const width of [360, 768]) for (const { format, value } of formats) test(`edits ${format} with a long key without clipping at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 640 })
  const item = { ...key('long-key', `LIPO_${'PROVIDER_CREDENTIAL_'.repeat(7)}`.slice(0, 128)), value_format: format }
  const state = await setup(page, { keys: [item], environment: 'production' })
  await expect(page.locator('#configuration-environment')).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: 'Draft', exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Manage values', exact: true }).click()
  const editor = page.getByRole('dialog', { name: 'Set value · production' })
  const identity = editor.getByRole('region', { name: 'Configuration key', exact: true })
  await expect(identity.locator('code')).toHaveText(item.key)
  const geometry = await identity.locator('code').evaluate(element => ({ height: element.getBoundingClientRect().height, line: parseFloat(getComputedStyle(element).lineHeight) }))
  expect(geometry.height).toBeLessThanOrEqual(geometry.line + 1)
  expect(await editor.evaluate(element => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  const input = editor.getByLabel('New secret value', { exact: true })
  await expect(input).toBeEnabled()
  if (['json', 'pem', 'string'].includes(format)) await expect(editor.locator('textarea')).toHaveCount(1)
  else await expect(editor.locator('input')).toHaveAttribute('type', 'password')
  const modalBounds = (await editor.boundingBox())!, inputBounds = (await input.boundingBox())!
  expect(inputBounds.width).toBeGreaterThan(modalBounds.width * 0.8)
  await input.fill(value)
  const save = editor.getByRole('button', { name: 'Save value', exact: true })
  await expect(save).toBeInViewport({ ratio: 1 })
  await save.click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(state.writes).toEqual([{ environment: 'production', revision: 0, value }])
  expect(state.keys[0].values.draft!.configured).toBe(false)
})

test('shows each environment independently and keeps restricted or read-only values protected', async ({ page }) => {
  const item = key('restricted', 'OPENROUTER_API_KEY')
  item.values.production = { configured: true, material: 'present', revision: 7, value_version: 'production-version' }
  const state = await setup(page, { keys: [item], environment: 'production', denied: ['draft'], readOnly: ['production'] })
  const row = page.getByRole('row').filter({ has: page.getByText(item.key, { exact: true }) })
  await expect(row.getByRole('cell', { name: /^Draft status:/ })).toHaveText('Unavailable or restricted')
  await expect(row.getByRole('cell', { name: /^Staging status:/ })).toHaveText('Not set')
  await expect(row.getByRole('cell', { name: /^Production status:/ })).toHaveText('Value saved')
  await page.getByRole('button', { name: 'Manage values', exact: true }).click()
  const editor = page.getByRole('dialog')
  await expect(editor.getByLabel('New secret value', { exact: true })).toBeDisabled()
  await editor.getByLabel('Environment', { exact: true }).selectOption('staging')
  await expect(editor.getByLabel('New secret value', { exact: true })).toBeEnabled()
  await editor.getByLabel('New secret value', { exact: true }).fill('synthetic-staging-token')
  await editor.getByRole('button', { name: 'Save value', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(state.writes).toEqual([{ environment: 'staging', revision: 0, value: 'synthetic-staging-token' }])
  expect(item.values.production.revision).toBe(7)
})
