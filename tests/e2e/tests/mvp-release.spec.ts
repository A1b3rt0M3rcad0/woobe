import { installApi, login, respond, workspace, project, user, now, productionAgent, selectedRelease } from '../fixtures/control-plane'
import { expect, test } from '@playwright/test'
import authorityFixture from '../fixtures/authority-categories.json'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

async function captureCli(page: import('@playwright/test').Page, name: string) {
  if(process.env.WOOBE_CAPTURE_AUXILIARY!=='1') return
  const directory=resolve(process.cwd(),'review-results/captures/flows/cli-keys')
  await mkdir(directory,{recursive:true})
  await page.screenshot({path:resolve(directory,`${name}.png`),animations:'disabled'})
}

test.use({ timezoneId: 'America/Sao_Paulo', locale: 'en-US' })

test('Overview explains unpriced Runs and opens Model pricing configuration', async ({ page }) => {
  await installApi(page)
  const fixture = structuredClone(projectOverviewFixture)
  Object.assign(fixture.summary, { terminal_agent_runs: 58, agent_run_cost_usd: null,
    priced_agent_runs: 0, unknown_agent_run_cost_count: 58, unknown_pricing_agent_runs: 58 })
  await page.route(`**/core/projects/${project.id}/overview*`, route => respond(route, fixture))
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}`)
  await expect(page.getByText('0/58 Runs priced · Partial')).toBeVisible()
  await expect(page.getByText(/Historical Runs without prices remain unknown/)).toBeHidden()
  await page.getByRole('button', { name: 'Runtime cost details' }).click()
  await expect(page.getByText(/Historical Runs without prices remain unknown/)).toBeVisible()
  await page.getByRole('button', { name: 'Review Model pricing' }).click()
  await expect(page).toHaveURL(/\/projects\/project-a\/models$/)
})

test('Overview preserves a genuinely priced zero cost', async ({ page }) => {
  await installApi(page)
  const fixture = structuredClone(projectOverviewFixture)
  Object.assign(fixture.summary, { agent_run_cost_usd: 0, unknown_agent_run_cost_count: 0 })
  await page.route(`**/core/projects/${project.id}/overview*`, route => respond(route, fixture))
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}`)
  await expect(page.getByText('All terminal Agent Runs priced')).toBeVisible()
  await expect(page.getByText('$0.00', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Review Model pricing' })).toHaveCount(0)
})

test('Overview keeps a new priced Run visible without a persistent historical warning', async ({ page }, testInfo) => {
  await installApi(page)
  const fixture = structuredClone(projectOverviewFixture)
  Object.assign(fixture.summary, { terminal_agent_runs: 65, agent_run_cost_usd: 0.0005,
    priced_agent_runs: 1, unknown_agent_run_cost_count: 64, unknown_pricing_agent_runs: 64 })
  await page.route(`**/core/projects/${project.id}/overview*`, route => respond(route, fixture))
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}`)
  await expect(page.getByText('1/65 Runs priced · Partial')).toBeVisible()
  await expect(page.getByText('$0.0005', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Review Model pricing' })).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath('runtime-cost-compact.png') })
  await page.getByRole('button', { name: 'Runtime cost details' }).click()
  await expect(page.getByRole('dialog', { name: 'Runtime cost coverage' })).toBeVisible()
  await expect(page.getByText(/64 Runs without frozen prices/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Runtime cost coverage' })).toBeHidden()
  await expect(page.getByRole('button', { name: 'Runtime cost details' })).toBeFocused()
})

test('bootstraps the first Woobe Core owner', async ({ page }) => {
  await installApi(page, { freshCore: true })
  await page.goto('/register')
  await page.getByPlaceholder('you@company.com').fill(user.email)
  await page.getByPlaceholder('At least 6 characters').fill('ReleaseGate123!')
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await expect(page).toHaveURL(/\/workspaces\/workspace-a\/setup/)
  await expect(page.getByRole('heading', { name: 'Create the Project for your Agent' })).toBeVisible()
})

test('opens a Project without edition-specific billing navigation', async ({ page }) => {
  await installApi(page)
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}`)
  await expect(page.getByText('Overview', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Billing', { exact: true })).toHaveCount(0)
})

test('lists and opens multiple Agent Networks', async ({ page }) => {
  await installApi(page)
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}/networks`)
  await expect(page.getByRole('heading', { name: 'Networks', level: 1 })).toBeVisible()
  await expect(page.getByText('Customer Support', { exact: true })).toBeVisible()
  await expect(page.getByText('Customer Onboarding', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Open Network workspace for Customer Support' }).click()
  await expect(page).toHaveURL(/\/networks\/network-support$/)
})

test('does not expose a foreign Project through routing', async ({ page }) => {
  await installApi(page)
  await login(page)
  const result = await page.evaluate(async () => {
    const response = await fetch('/core/projects/project-b')
    return { status: response.status, body: await response.json() }
  })
  expect(result.status).toBe(404)
  expect(result.body).toMatchObject({ success: false, message: 'Resource not found' })
})

test('owner creates, copies, rotates and revokes a CLI key in Workspace settings', async ({ page }) => {
  await page.setViewportSize({ width: 1198, height: 720 })
  await page.clock.setFixedTime(new Date('2026-10-06T15:00:00Z'))
  await installApi(page)
  const secret = 'woobe_control_browser_test_secret'
  const keyPath = `/core/workspaces/${workspace.id}/control-keys`
  const headers: Record<string, string>[] = []
  const creations: Record<string, unknown>[] = []
  let keys: Record<string, unknown>[] = []
  const metadata = {
    id: 'key-a', name: 'My workstation', description: null, key_prefix: 'woobe_control_prefix',
    status: 'active', permissions: ['workspace:read'], project_grants: [],
    on_project_create_permissions: [], created_at: now, expires_at: null,
    etag: '"control-key:key-a:1"',
  }
  await page.route('**/identity/access/me*', (route) => respond(route, {
    permissions: [...authorityFixture.permissions.workspace, ...authorityFixture.permissions.project], conditions: {},
  }))
  await page.route('**/identity/permissions', (route) => respond(route, {
    permissions: authorityFixture.permissions,
  }))
  await page.route(`**/identity/workspaces/${workspace.id}/authority-categories*`, route => respond(route, { items: [], system_categories: authorityFixture.categories, complete: true, next_cursor: null }))
  await page.route(`**/core/workspaces/${workspace.id}/project-access`, (route) => respond(route, [project]))
  await page.route(new RegExp(`${keyPath}(?:/.*)?$`), async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === 'GET') return respond(route, keys)
    headers.push(request.headers())
    if (path.endsWith('/rotate')) {
      keys = [{ ...metadata, status: 'revoked' }, { ...metadata, id: 'key-b', etag: '"control-key:key-b:2"' }]
      return respond(route, { ...keys[1], key: `${secret}_rotated` }, 201)
    }
    if (path.endsWith('/revoke')) {
      keys = keys.map((key) => ({ ...key, status: 'revoked' }))
      return respond(route, keys[1])
    }
    expect(request.postDataJSON()).toMatchObject({ name: 'My workstation', permissions: [],
      project_grants: [expect.objectContaining({ project_id: project.id, category_revision: 1 })] })
    const body = request.postDataJSON()
    creations.push(body)
    keys = [{ ...metadata, ...body }]
    return respond(route, { ...keys[0], key: secret }, 201)
  })
  await login(page)
  await page.getByRole('button', { name: /Workspace settings/ }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'CLI Keys', exact: true }).click()
  await dialog.getByRole('button', { name: 'Create CLI key' }).click()
  await dialog.getByLabel('Name', { exact: true }).fill('My workstation')
  await dialog.getByRole('button', { name: 'Project Reader', exact: true }).click()
  await expect(dialog.locator('input[type="datetime-local"], input[type="date"], input[type="time"]')).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Increase hour' })).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Increase minute' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Next month' }).click()
  await dialog.getByRole('button', { name: 'Feb 10, 2027', exact: true }).click()
  const accessBox = await dialog.getByText('Roles and access', { exact: true }).boundingBox()
  const expirationBox = await dialog.getByText('Expiration', { exact: true }).boundingBox()
  expect(expirationBox!.x).toBeGreaterThan(accessBox!.x + 300)
  expect(Math.abs(expirationBox!.y - accessBox!.y)).toBeLessThan(5)
  const nameBox = await dialog.getByLabel('Name', { exact: true }).boundingBox()
  const descriptionBox = await dialog.getByLabel(/Description/).boundingBox()
  expect(descriptionBox!.x).toBeGreaterThan(nameBox!.x + 200)
  expect(Math.abs(descriptionBox!.y - nameBox!.y)).toBeLessThan(5)
  await page.screenshot({ path: test.info().outputPath('workspace-cli-keys.png') })
  await captureCli(page,'create')
  await expect(dialog.getByRole('button', { name: 'Create key', exact: true })).toBeInViewport({ ratio: 1 })
  await dialog.getByRole('button', { name: 'Create key', exact: true }).click()
  await expect(dialog.getByText(secret, { exact: true })).toBeVisible()
  await captureCli(page,'synthetic-secret')
  await expect(dialog.getByRole('button', { name: 'Copy Control Key' })).toBeVisible()
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(page.url()).origin })
  await dialog.getByRole('button', { name: 'Copy Control Key' }).click()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(secret)
  await dialog.getByRole('button', { name: 'I saved the key' }).click()
  await expect(dialog.getByText(secret, { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Rotate My workstation' }).click()
  await captureCli(page,'rotation-confirmation')
  await dialog.getByRole('button', { name: 'Confirm rotation' }).click()
  await expect(dialog.getByText(`${secret}_rotated`, { exact: true })).toBeVisible()
  await captureCli(page,'rotation-synthetic-secret')
  await dialog.getByRole('button', { name: 'Overview', exact: true }).click()
  await dialog.getByRole('button', { name: 'CLI Keys', exact: true }).click()
  await expect(dialog.getByText(`${secret}_rotated`, { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Revoke My workstation' }).click()
  await captureCli(page,'revocation-confirmation')
  await dialog.getByRole('button', { name: 'Confirm revocation' }).click()
  await expect(dialog.getByRole('button', { name: 'Revoke My workstation' })).toHaveCount(0)
  expect(creations[0]['expires_at']).toBe('2027-02-11T03:00:00.000Z')
  expect(creations[0]['project_grants']).toEqual([expect.objectContaining({ category_id: authorityFixture.categories.find(role => role.name === 'project-reader')!.id, category_revision: 1 })])
  expect(headers[0]['idempotency-key']).toBeTruthy()
  expect(headers[1]['if-match']).toBe(metadata.etag)
  expect(headers[1]['idempotency-key']).toBeTruthy()
  expect(headers[2]['if-match']).toBe('"control-key:key-b:2"')
})


test('ASaC selection drives cards, playground, history, API and Runtime Key creation', async ({ page }) => {
  await installApi(page, { asacAgent: true })
  const catalogReads: string[] = []
  page.on('request', request => { if (new URL(request.url()).pathname.endsWith('/releases')) catalogReads.push(request.url()) })
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}/agents`)
  await expect(page.getByLabel('Production Enabled', { exact: true })).toBeVisible()
  expect(catalogReads).toHaveLength(0) // Cards don't fetch full snapshot catalogs.
  await page.getByRole('button', { name: `Open Agent playground for ${productionAgent.name}` }).click()
  await page.getByRole('group', { name: 'Agent environment' }).getByRole('button', { name: 'PRODUCTION', exact: true }).click()
  await expect(page.getByText('Using: Production · 1.2.0', { exact: true })).toBeVisible()
  await expect(page.locator('header').getByText('custom / frozen-release-model', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeDisabled() // Empty composer only.
  await page.locator('textarea').first().fill('ping')
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Manage Agent', exact: true }).click()
  const manager = page.getByRole('dialog')
  await expect(manager.getByText('Production · 1.2.0', { exact: true })).toBeVisible()
  await manager.getByRole('button', { name: /Activity/ }).click()
  await expect(manager.getByText('Initial deployment', { exact: true }).first()).toBeVisible()
  await manager.getByRole('button', { name: 'Close', exact: true }).last().click()
  await page.getByRole('button', { name: 'API', exact: true }).click()
  const reference = page.getByRole('dialog')
  await expect(reference.getByText('frozen-release-model', { exact: true })).toBeVisible()
  await expect(reference.getByText('stateless', { exact: true })).toBeVisible()
  await reference.getByRole('button', { name: 'Create Runtime Key' }).click()
  const issuance = page.getByRole('dialog').last()
  await expect(issuance.getByText('Deployment available', { exact: true })).toBeVisible()
  await expect(issuance).toContainText('Agent · Production · Runtime Key')
  await expect(issuance.getByText('Not deployed', { exact: true })).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath('asac-production-key.png'), fullPage: true })
})

for (const scenario of [
  { title: 'failed selection', options: { productionError: true }, pill: 'Production Unknown', message: 'selection unavailable' },
  { title: 'disabled runtime', options: { runtimeEnabled: false }, pill: 'Production Off', message: 'runtime is off' },
  { title: 'forbidden details', options: { detailsError: true }, pill: 'Production Enabled', message: 'details unavailable' },
]) {
  test(`ASaC ${scenario.title} never becomes No Production`, async ({ page }) => {
    await installApi(page, { asacAgent: true, ...scenario.options }); await login(page)
    await page.goto(`/workspaces/${workspace.id}/projects/${project.id}/agents`)
    await expect(page.getByLabel(scenario.pill, { exact: true })).toBeVisible()
    await expect(page.getByLabel('No Production', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: `Open Agent playground for ${productionAgent.name}` }).click()
    await page.getByRole('group', { name: 'Agent environment' }).getByRole('button', { name: 'PRODUCTION', exact: true }).click()
    await expect(page.getByText(scenario.message, { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeDisabled()
  })
}


test('general Runtime Key dialog keeps Production when it cannot observe deployment', async ({ page }) => {
  await installApi(page, { asacAgent: true, productionError: true }); await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}/api-keys?type=runtime&targetType=agent`)
  await page.getByRole('button', { name: 'Create Agent Runtime Key', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: /ASaC Production Agent/ }).click()
  await expect(dialog.getByText('Deployment unknown', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Production', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(dialog.getByRole('button', { name: 'Staging', exact: true })).toHaveAttribute('aria-pressed', 'false')
})
