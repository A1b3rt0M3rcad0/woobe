import { test, expect, type Page } from '@playwright/test'
import { installApi, login, project, workspace, respond } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'
import type { ConfigurationKey } from '../../../packages/woobe-frontend/src/features/projects/configuration'

const root = `/workspaces/${workspace.id}/projects/${project.id}/environments`
const empty = { configured: false, material: 'missing' as const, revision: 0, value_version: null }
const key = (id: string, name: string, count = 0): ConfigurationKey => ({
  id, key: name, kind: 'secret', description: 'Synthetic configuration', value_format: 'token', definition_revision: 1,
  origin: 'manual', material: 'missing', used_by_count: count, values: { draft: { ...empty }, staging: { ...empty }, production: { ...empty } },
})

async function setup(page: Page, race = false) {
  await installApi(page); await installResources(page)
  const keys = [key('used', 'USED_KEY', 1), key('unused', 'UNUSED_KEY')]
  const writes: { environment: string; revision: number; value: string }[] = []
  const events: string[] = []
  await page.route('**/core/projects/project-a/configuration/**', async route => {
    const url = new URL(route.request().url()), method = route.request().method()
    const suffix = url.pathname.split('/configuration/')[1]
    if (suffix === 'keys' && method === 'GET') {
      const environment = (url.searchParams.get('environment') ?? 'draft') as 'draft' | 'staging' | 'production'
      const search = url.searchParams.get('search') ?? ''
      const items = keys.filter(item => item.key.includes(search)).map(item => ({ ...item,
        material: item.values[environment]!.material, values: { [environment]: item.values[environment] } }))
      return respond(route, { items, total: items.length, offset: 0, limit: 50, has_next: false, environment,
        permissions: { declare: true, 'value:write': true, 'value:clear': true } })
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
      if (race) item.used_by_count = 1
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
  await page.goto(root)
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
  await expect(page.locator('#configuration-environment')).toHaveValue('draft')
  await editor.getByLabel('New secret value').fill('synthetic-staging-only')
  await editor.getByRole('button', { name: 'Save value', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('#configuration-environment')).toHaveValue('staging')
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
  const state = await setup(page, true)
  await page.getByRole('button', { name: 'Delete UNUSED_KEY', exact: true }).click()
  const deletion = page.getByRole('dialog', { name: 'Delete key · UNUSED_KEY' })
  await expect(deletion.getByRole('button', { name: 'Delete key', exact: true })).toBeEnabled()
  await deletion.getByRole('button', { name: 'Delete key', exact: true }).click()
  await expect(deletion.getByText('This key is in use. You can edit it, but cannot delete it.')).toBeVisible()
  await expect(deletion.getByRole('button', { name: 'Delete key', exact: true })).toBeDisabled()
  expect(state.keys.some(item => item.id === 'unused')).toBe(true)
})
