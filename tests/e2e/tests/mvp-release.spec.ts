import { expect, test, type Page, type Route } from '@playwright/test'
import authorityFixture from '../fixtures/authority-categories.json'

test.use({ timezoneId: 'America/Sao_Paulo', locale: 'en-US' })

const now = new Date().toISOString()
const user = { id: 'user-a', email: 'owner-a@example.test', status: 'active' }
const workspace = {
  id: 'workspace-a', name: 'Woobe Test Workspace', slug: 'woobe-test', status: 'active',
  membership_role: 'owner', can_manage_workspace: true, accessible_project_count: 1,
  access_mode: 'implicit_owner',
}
const project = {
  id: 'project-a', workspace_id: workspace.id, name: 'Release Project',
  slug: 'release-project', status: 'active', workspace_role: 'owner', access_source: 'workspace',
}
const emptyNetworkDefinition = {
  schema_version: 2,
  root_node_id: '',
  nodes: [],
  edges: [],
  settings: { session_mode: 'stateful', max_depth: 8, max_invocations: 32, timeout_seconds: 120 },
}
const networks = [
  {
    id: 'network-support', project_id: project.id, name: 'Customer Support',
    description: 'Handles customer requests.', draft_definition: emptyNetworkDefinition,
    draft_revision: 0, staging_version_id: null, production_version_id: null,
    agent_count: 0, created_at: now, updated_at: now,
  },
  {
    id: 'network-onboarding', project_id: project.id, name: 'Customer Onboarding',
    description: 'Guides new customers.', draft_definition: emptyNetworkDefinition,
    draft_revision: 0, staging_version_id: null, production_version_id: null,
    agent_count: 0, created_at: now, updated_at: now,
  },
]

const overview = {
  project_id: project.id, generated_at: now, from: now, to: now,
  bucket: 'hour', environment: 'all',
  summary: {
    active_agents: 0, production_agents: 0, network_count: networks.length,
    staging_networks: 0, production_networks: 0, network_runs: 0,
    failed_network_runs: 0, requests: 0, request_change_percent: 0,
    avg_latency_ms: 0, p95_latency_ms: 0, success_rate: 100,
    failed_requests: 0, cost_usd: 0, unknown_cost_count: 0,
  },
  timeseries: [],
  environment_distribution: { draft: 0, staging: 0, production: 0 },
  recent_releases: [], recent_traces: [],
  knowledge_summary: {
    collections: 0, documents: 0, indexed_documents: 0,
    failed_documents: 0, storage_bytes: 0, pending_documents: 0,
  },
  tools_summary: { total: 0, active: 0, inactive: 0, recent_failures: [] },
  capabilities: { sessions_jobs: true, ingestion_pipeline: false, activity_feed: false },
}

async function respond(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(status < 400
      ? { success: true, message: 'ok', data }
      : { success: false, message: 'Resource not found', data: null }),
  })
}

async function installApi(page: Page, options?: { freshCore?: boolean }) {
  const freshCore = options?.freshCore ?? false

  await page.route('**/*', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const prefixes = ['/identity', '/core', '/ai', '/runtime', '/observability', '/knowledge', '/tools', '/network', '/metering']
    if (!prefixes.some((prefix) => path.startsWith(prefix))) {
      await route.continue()
      return
    }

    if (path === '/identity/instance/status') {
      await respond(route, {
        initialized: !freshCore,
        edition: 'core',
        signup_mode: freshCore ? 'bootstrap' : 'invite_only',
        telemetry_enabled: false,
        requires_existing_owner_bootstrap: false,
      })
    } else if (path === '/identity/instance/bootstrap' && method === 'POST') {
      await respond(route, {
        token_type: 'Bearer', expires_in: 900, csrf: 'csrf-test', user, workspace,
      }, 201)
    } else if (path === '/identity/auth/login' && method === 'POST') {
      await respond(route, { token_type: 'Bearer', expires_in: 900, csrf: 'csrf-test', user })
    } else if (path === '/identity/users/me') {
      await respond(route, user)
    } else if (path === '/identity/workspaces') {
      await respond(route, [workspace])
    } else if (path === `/identity/workspaces/${workspace.id}`) {
      await respond(route, workspace)
    } else if (path === '/core/projects' && method === 'GET') {
      await respond(route, [project])
    } else if (path === `/core/projects/${project.id}`) {
      await respond(route, project)
    } else if (path === `/core/projects/${project.id}/overview`) {
      await respond(route, overview)
    } else if (path === `/network/projects/${project.id}/networks` && method === 'GET') {
      await respond(route, networks)
    } else if (path.startsWith(`/network/projects/${project.id}/networks/`) && method === 'GET') {
      const networkId = path.split('/').at(-1)
      const network = networks.find((item) => item.id === networkId)
      await respond(route, network ?? null, network ? 200 : 404)
    } else if (/^\/network\/[^/]+\/runtime-environments$/.test(path)) {
      await respond(route, { draft: { enabled: true }, staging: { enabled: false }, production: { enabled: false } })
    } else if (/^\/network\/[^/]+\/management\/(versions|activations)$/.test(path)) {
      await respond(route, [])
    } else if (/^\/network\/[^/]+\/sessions$/.test(path)) {
      await respond(route, [])
    } else if (path === '/core/projects/project-b' || path.startsWith('/core/projects/project-b/')) {
      await respond(route, null, 404)
    } else {
      await respond(route, [])
    }
  })
}

async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('you@company.com').fill(user.email)
  await page.getByPlaceholder('Enter your password').fill('ReleaseGate123!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/workspaces\/workspace-a\/projects\/project-a|\/dashboard/)
}

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
  await expect(dialog.getByRole('button', { name: 'Create key', exact: true })).toBeInViewport({ ratio: 1 })
  await dialog.getByRole('button', { name: 'Create key', exact: true }).click()
  await expect(dialog.getByText(secret, { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Copy Control Key' })).toBeVisible()
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(page.url()).origin })
  await dialog.getByRole('button', { name: 'Copy Control Key' }).click()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(secret)
  await dialog.getByRole('button', { name: 'I saved the key' }).click()
  await expect(dialog.getByText(secret, { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Rotate My workstation' }).click()
  await dialog.getByRole('button', { name: 'Confirm rotation' }).click()
  await expect(dialog.getByText(`${secret}_rotated`, { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Overview', exact: true }).click()
  await dialog.getByRole('button', { name: 'CLI Keys', exact: true }).click()
  await expect(dialog.getByText(`${secret}_rotated`, { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Revoke My workstation' }).click()
  await dialog.getByRole('button', { name: 'Confirm revocation' }).click()
  await expect(dialog.getByRole('button', { name: 'Revoke My workstation' })).toHaveCount(0)
  expect(creations[0]['expires_at']).toBe('2027-02-11T03:00:00.000Z')
  expect(creations[0]['project_grants']).toEqual([expect.objectContaining({ category_id: authorityFixture.categories.find(role => role.name === 'project-reader')!.id, category_revision: 1 })])
  expect(headers[0]['idempotency-key']).toBeTruthy()
  expect(headers[1]['if-match']).toBe(metadata.etag)
  expect(headers[1]['idempotency-key']).toBeTruthy()
  expect(headers[2]['if-match']).toBe('"control-key:key-b:2"')
})
