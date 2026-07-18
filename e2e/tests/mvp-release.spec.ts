import { expect, test, type Page, type Route } from '@playwright/test'

const now = new Date().toISOString()
const user = { id: 'user-a', email: 'owner-a@example.test', status: 'active' }
const organization = { id: 'org-a', name: 'Tenant A', slug: 'tenant-a', status: 'active' }
const project = {
  id: 'project-a', organization_id: 'org-a', name: 'Release Project',
  slug: 'release-project', status: 'active',
}
const credential = {
  id: 'credential-a', project_id: project.id, provider: 'openai',
  name: 'Deterministic OpenAI', status: 'active', metadata: {},
}
const agent = {
  id: 'agent-a', project_id: project.id, provider_credential_id: credential.id,
  name: 'Release Gate Agent', description: 'Deterministic release agent',
  type: 'assistant', system_prompt: 'Be deterministic.', provider: 'openai',
  model: 'gpt-4o-mini', temperature: 0.2, max_output_tokens: 128,
  session_mode: 'stateful', status: 'active', settings: {},
}
const emptyNetworkDefinition = {
  schema_version: 2,
  root_node_id: '',
  nodes: [],
  edges: [],
  settings: {
    session_mode: 'stateful',
    max_depth: 8,
    max_invocations: 32,
    timeout_seconds: 120,
  },
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
    active_agents: 1, production_agents: 1, network_count: networks.length,
    staging_networks: 0, production_networks: 0, network_runs: 0,
    failed_network_runs: 0, requests: 2, request_change_percent: 100,
    avg_latency_ms: 42, p95_latency_ms: 50, success_rate: 100,
    failed_requests: 0, cost_usd: 0.001, unknown_cost_count: 0,
  },
  timeseries: [{
    bucket_start: now, requests: 2, success: 2, failed: 0,
    avg_latency_ms: 42, p95_latency_ms: 50, input_tokens: 14,
    output_tokens: 10, cost_usd: 0.001, unknown_cost_count: 0,
  }],
  environment_distribution: { draft: 0, staging: 0, production: 1 },
  recent_releases: [],
  recent_traces: [{
    id: 'trace-a', agent_id: agent.id, agent_name: agent.name,
    environment: 'production', status: 'completed', latency_ms: 42,
    total_tokens: 12, cost_usd: 0.001, cost_known: true, started_at: now,
  }],
  knowledge_summary: {
    collections: 0, documents: 0, indexed_documents: 0,
    failed_documents: 0, storage_bytes: 0, pending_documents: 0,
  },
  tools_summary: { total: 0, active: 0, inactive: 0, recent_failures: [] },
  capabilities: { sessions_jobs: true, ingestion_pipeline: false, activity_feed: false },
}

async function respond(route: Route, data: unknown, status = 200) {
  const body = status < 400
    ? { success: true, message: 'ok', data }
    : { success: false, message: 'Resource not found', data: null }
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function installApi(page: Page) {
  let streamed = false
  let apiKeys: unknown[] = []

  await page.route('**/*', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const prefixes = ['/identity', '/core', '/ai', '/runtime', '/observability', '/knowledge', '/tools', '/network']
    if (!prefixes.some((prefix) => path.startsWith(prefix))) {
      await route.continue()
      return
    }

    if (method === 'POST' && ['/identity/auth/register', '/identity/auth/login'].includes(path)) {
      await respond(route, { token: 'test-session-token', user })
    } else if (path === '/identity/users/me') {
      await respond(route, user)
    } else if (path === '/identity/organizations') {
      await respond(route, [organization])
    } else if (path === `/identity/organizations/${organization.id}`) {
      await respond(route, organization)
    } else if (path === '/core/projects' && method === 'GET') {
      await respond(route, [project])
    } else if (path === '/core/projects/project-b' || path.startsWith('/core/projects/project-b/')) {
      await respond(route, null, 404)
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
    } else if (/^\/network\/[^/]+\/management\/(versions|activations)$/.test(path)) {
      await respond(route, [])
    } else if (/^\/network\/[^/]+\/sessions$/.test(path)) {
      await respond(route, [])
    } else if (path === '/ai/credentials') {
      await respond(route, [credential])
    } else if (path === '/ai/agents' && method === 'POST') {
      await respond(route, agent)
    } else if (path === '/ai/agents' && method === 'GET') {
      await respond(route, [agent])
    } else if (path === `/ai/agents/${agent.id}`) {
      await respond(route, agent)
    } else if (path === `/ai/agents/${agent.id}/releases`) {
      await respond(route, [])
    } else if (path === `/runtime/agents/${agent.id}/sessions`) {
      await respond(route, streamed ? [{
        id: 'session-a', project_id: project.id, agent_id: agent.id,
        status: 'active', external_session_id: 'e2e-session',
        tenant_id: 'tenant-a', user_id: user.id, message_count: 2,
        created_at: now, last_message_at: now,
      }] : [])
    } else if (path === '/runtime/sessions/session-a/messages') {
      await respond(route, streamed ? [
        { id: 'message-user', role: 'user', content: 'Run release gate', data: {} },
        { id: 'message-assistant', role: 'assistant', content: 'ProjectRAI release gate passed', data: {} },
      ] : [])
    } else if (path === '/runtime/ask/stream' && method === 'POST') {
      streamed = true
      const usage = { input_tokens: 7, output_tokens: 5, total_tokens: 12, cost_usd: 0.001 }
      const events = [
        { protocol_version: 1, type: 'meta', session_id: 'session-a', trace_id: 'trace-a', request_id: 'request-a' },
        { protocol_version: 1, type: 'token', content: 'ProjectRAI ' },
        { protocol_version: 1, type: 'token', content: 'release gate passed' },
        { protocol_version: 1, type: 'usage', usage },
        {
          protocol_version: 1, type: 'done', answer: 'ProjectRAI release gate passed',
          session_id: 'session-a', message_id: 'message-assistant', trace_id: 'trace-a',
          provider: 'fake', model: 'fake-stream', latency_ms: 42, ttft_ms: 5,
          usage, sources: [], tool_calls: [], execution_events: [],
        },
      ]
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
      })
    } else if (path.includes('/traces')) {
      await respond(route, streamed ? [{ id: 'trace-a', project_id: project.id, agent_id: agent.id, status: 'completed' }] : [])
    } else if (path === `/core/projects/${project.id}/api-keys` && method === 'GET') {
      await respond(route, apiKeys)
    } else if (path === `/core/projects/${project.id}/api-keys` && method === 'POST') {
      const created = {
        id: 'key-a', project_id: project.id, name: 'Release key',
        key_prefix: 'test_release', key: 'release-key-visible-once',
        scopes: ['runtime:execute'], status: 'active',
      }
      apiKeys = [created]
      await respond(route, created)
    } else {
      await respond(route, [])
    }
  })
}

async function authenticate(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('projectrai_token', 'test-session-token')
    localStorage.setItem('projectrai_org', JSON.stringify({ id: 'org-a', name: 'Tenant A', slug: 'tenant-a' }))
    localStorage.setItem('projectrai_project', JSON.stringify({
      id: 'project-a', organization_id: 'org-a', name: 'Release Project', slug: 'release-project',
    }))
  })
}

test('onboards a tenant and renders the live project dashboard', async ({ page }) => {
  await installApi(page)
  await page.goto('/register')
  await page.getByPlaceholder('you@company.com').fill(user.email)
  await page.getByPlaceholder('At least 6 characters').fill('ReleaseGate123!')
  await page.getByPlaceholder('Your company name').fill(organization.name)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(/\/organizations$/)
  await page.getByRole('button', { name: 'Select', exact: true }).click()
  await expect(page).toHaveURL(/\/organizations\/org-a\/projects$/)
  await page.getByRole('button', { name: /^Open/ }).click()
  await expect(page).toHaveURL(/\/organizations\/org-a\/projects\/project-a$/)
  await expect(page.getByText('Runtime Requests', { exact: true }).first()).toBeVisible()
})

test('creates an agent streams reloads history and creates an API key', async ({ page }) => {
  await installApi(page)
  await authenticate(page)
  await page.goto('/organizations/org-a/projects/project-a/agents/new')
  await page.getByPlaceholder('My Agent').fill(agent.name)
  await page.locator('select').first().selectOption(credential.id)
  await page.locator('select').first().selectOption(agent.model)
  await page.getByRole('button', { name: 'Create Agent' }).click()
  await expect(page).toHaveURL(/\/agents\/agent-a\/playground$/)
  await page.getByPlaceholder('Type your message...').fill('Run release gate')
  await page.getByPlaceholder('Type your message...').press('Enter')
  await expect(page.getByText('ProjectRAI release gate passed').last()).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Sessions' }).click()
  await page.getByRole('button', { name: /session-/ }).click()
  await expect(page.getByText('ProjectRAI release gate passed').last()).toBeVisible()
  await page.goto('/organizations/org-a/projects/project-a/api-keys')
  await page.getByRole('button', { name: 'Create Key' }).first().click()
  await page.getByPlaceholder('Key name').fill('Release key')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.getByText('release-key-visible-once')).toBeVisible()
})

test('lists and opens multiple Networks without an implicit default', async ({ page }) => {
  await installApi(page)
  await authenticate(page)
  await page.goto('/organizations/org-a/projects/project-a/networks')

  await expect(page.getByRole('heading', { name: 'Networks' })).toBeVisible()
  await expect(page.getByText('Customer Support', { exact: true })).toBeVisible()
  await expect(page.getByText('Customer Onboarding', { exact: true })).toBeVisible()

  await page.locator('article').filter({ hasText: 'Customer Support' })
    .getByRole('button', { name: 'Open workspace' }).click()
  await expect(page).toHaveURL(/\/networks\/network-support$/)

  await page.getByRole('button', { name: 'Back to Networks' }).click()
  await expect(page).toHaveURL(/\/projects\/project-a\/networks$/)

  await page.locator('article').filter({ hasText: 'Customer Onboarding' })
    .getByRole('button', { name: 'Open workspace' }).click()
  await expect(page).toHaveURL(/\/networks\/network-onboarding$/)
})

test('returns not found for a foreign project without tenant leakage', async ({ page }) => {
  await installApi(page)
  await authenticate(page)
  await page.goto('/organizations')
  const result = await page.evaluate(async () => {
    const response = await fetch('/core/projects/project-b')
    return { status: response.status, body: await response.json() }
  })
  expect(result.status).toBe(404)
  expect(result.body).toMatchObject({ success: false, message: 'Resource not found' })
  await page.goto('/organizations/org-a/projects/project-b')
  await expect(page.getByText('Dashboard unavailable')).toBeVisible()
  await expect(page.getByText('Tenant B secret')).toHaveCount(0)
})
