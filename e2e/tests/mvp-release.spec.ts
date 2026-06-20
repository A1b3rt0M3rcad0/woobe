import { expect, test, type Page, type Route } from '@playwright/test'

const user = { id: 'user-a', email: 'owner-a@example.test', status: 'active' }
const organization = { id: 'org-a', name: 'Tenant A', slug: 'tenant-a', status: 'active' }
const project = { id: 'project-a', organization_id: 'org-a', name: 'Release Project', slug: 'release-project', status: 'active' }
const credential = {
  id: 'credential-a',
  project_id: 'project-a',
  provider: 'openai',
  name: 'Deterministic OpenAI',
  status: 'active',
  metadata: {},
}
const agent = {
  id: 'agent-a',
  project_id: 'project-a',
  provider_credential_id: 'credential-a',
  name: 'Release Gate Agent',
  description: 'Deterministic release agent',
  type: 'assistant',
  system_prompt: 'Be deterministic.',
  provider: 'openai',
  model: 'gpt-4o-mini',
  temperature: 0.2,
  max_output_tokens: 128,
  session_mode: 'stateful',
  status: 'active',
  settings: {},
}

function envelope(data: unknown, message = 'ok') {
  return { success: true, message, data }
}

function overview() {
  const now = new Date().toISOString()
  return {
    project_id: project.id,
    generated_at: now,
    from: now,
    to: now,
    bucket: 'hour',
    environment: 'all',
    summary: {
      active_agents: 1,
      production_agents: 1,
      requests: 2,
      request_change_percent: 100,
      avg_latency_ms: 42,
      p95_latency_ms: 50,
      success_rate: 100,
      failed_requests: 0,
      cost_usd: 0.001,
      unknown_cost_count: 0,
    },
    timeseries: [{
      bucket_start: now,
      requests: 2,
      success: 2,
      failed: 0,
      avg_latency_ms: 42,
      p95_latency_ms: 50,
      input_tokens: 14,
      output_tokens: 10,
      cost_usd: 0.001,
      unknown_cost_count: 0,
    }],
    environment_distribution: { draft: 0, staging: 0, production: 1 },
    recent_releases: [],
    recent_traces: [{
      id: 'trace-a',
      agent_id: agent.id,
      agent_name: agent.name,
      environment: 'production',
      status: 'completed',
      latency_ms: 42,
      total_tokens: 12,
      cost_usd: 0.001,
      cost_known: true,
      started_at: now,
    }],
    knowledge_summary: {
      collections: 0,
      documents: 0,
      indexed_documents: 0,
      failed_documents: 0,
      storage_bytes: 0,
      pending_documents: 0,
    },
    tools_summary: { total: 0, active: 0, inactive: 0, recent_failures: [] },
    capabilities: { sessions_jobs: true, ingestion_pipeline: false, activity_feed: false },
  }
}

async function json(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(status < 400 ? envelope(data) : { success: false, message: 'Resource not found', data: null }),
  })
}

async function installDeterministicApi(page: Page) {
  let streamed = false
  let apiKeys: unknown[] = []

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (!path.startsWith('/identity') && !path.startsWith('/core') && !path.startsWith('/ai')
      && !path.startsWith('/runtime') && !path.startsWith('/observability') && !path.startsWith('/knowledge')
      && !path.startsWith('/tools')) {
      await route.continue()
      return
    }

    if (method === 'POST' && (path === '/identity/auth/register' || path === '/identity/auth/login')) {
      await json(route, { token: 'e2e-access-token', user })
      return
    }
    if (path === '/identity/users/me') {
      await json(route, user)
      return
    }
    if (path === '/identity/organizations') {
      await json(route, [organization])
      return
    }
    if (path === `/identity/organizations/${organization.id}`) {
      await json(route, organization)
      return
    }
    if (path === '/core/projects' && method === 'GET') {
      await json(route, [project])
      return
    }
    if (path === `/core/projects/${project.id}`) {
      await json(route, project)
      return
    }
    if (path === '/core/projects/project-b' || path.startsWith('/core/projects/project-b/')) {
      await json(route, null, 404)
      return
    }
    if (path === `/core/projects/${project.id}/overview`) {
      await json(route, overview())
      return
    }
    if (path === `/core/projects/${project.id}/provider-credentials`) {
      await json(route, [credential])
      return
    }
    if (path === '/ai/agents' && method === 'POST') {
      await json(route, agent)
      return
    }
    if (path === '/ai/agents' && method === 'GET') {
      await json(route, [agent])
      return
    }
    if (path === `/ai/agents/${agent.id}`) {
      await json(route, agent)
      return
    }
    if (path === `/ai/agents/${agent.id}/releases`) {
      await json(route, [])
      return
    }
    if (path === `/runtime/agents/${agent.id}/sessions`) {
      await json(route, streamed ? [{
        id: 'session-a', project_id: project.id, agent_id: agent.id, status: 'active',
        external_session_id: 'e2e-session', tenant_id: 'tenant-a', user_id: user.id,
        created_at: new Date().toISOString(), last_message_at: new Date().toISOString(),
      }] : [])
      return
    }
    if (path === '/runtime/sessions/session-a/messages') {
      await json(route, streamed ? [
        { id: 'message-user', role: 'user', content: 'Run release gate', data: {} },
        { id: 'message-assistant', role: 'assistant', content: 'ProjectRAI release gate passed', data: { model: 'fake-stream', provider: 'fake' } },
      ] : [])
      return
    }
    if (path === '/runtime/ask/stream' && method === 'POST') {
      streamed = true
      const events = [
        { protocol_version: 1, type: 'meta', session_id: 'session-a', trace_id: 'trace-a', request_id: 'request-a' },
        { protocol_version: 1, type: 'token', content: 'ProjectRAI ' },
        { protocol_version: 1, type: 'token', content: 'release gate passed' },
        { protocol_version: 1, type: 'usage', usage: { input_tokens: 7, output_tokens: 5, total_tokens: 12, cost_usd: 0.001 } },
        {
          protocol_version: 1, type: 'done', answer: 'ProjectRAI release gate passed',
          session_id: 'session-a', message_id: 'message-assistant', trace_id: 'trace-a',
          provider: 'fake', model: 'fake-stream', latency_ms: 42, ttft_ms: 5,
          usage: { input_tokens: 7, output_tokens: 5, total_tokens: 12, cost_usd: 0.001 },
          sources: [], tool_calls: [], execution_events: [],
        },
      ]
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
      })
      return
    }
    if (path.includes('/traces')) {
      await json(route, streamed ? [{ id: 'trace-a', project_id: project.id, agent_id: agent.id, status: 'completed' }] : [])
      return
    }
    if (path === `/core/projects/${project.id}/api-keys` && method === 'GET') {
      await json(route, apiKeys)
      return
    }
    if (path === `/core/projects/${project.id}/api-keys` && method === 'POST') {
      const created = {
        id: 'key-a', project_id: project.id, name: 'Release key', key_prefix: 'rai_live_e2e',
        key: 'rai_live_e2e_deterministic-secret', scopes: ['runtime:execute'], status: 'active',
      }
      apiKeys = [created]
      await json(route, created)
      return
    }

    await json(route, [])
  })
}

test('onboards a tenant and renders the live project dashboard', async ({ page }) => {
  await installDeterministicApi(page)
  await page.goto('/register')
  await page.getByPlaceholder('you@company.com').fill(user.email)
  await page.getByPlaceholder('At least 6 characters').fill('ReleaseGate123!')
  await page.getByPlaceholder('Your company name').fill(organization.name)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/organizations$/)
  await expect(page.getByText('Tenant A')).toBeVisible()
  await page.getByRole('button', { name: /^Select/ }).click()
  await expect(page).toHaveURL(/\/organizations\/org-a\/projects$/)
  await page.getByRole('button', { name: /^Open/ }).click()
  await expect(page).toHaveURL(/\/organizations\/org-a\/projects\/project-a$/)
  await expect(page.getByText('Requests').first()).toBeVisible()
  await expect(page.getByText('100%').first()).toBeVisible()
})

test('creates an agent, streams a session, reloads history and creates an API key', async ({ page }) => {
  await installDeterministicApi(page)
  await page.addInitScript(() => {
    localStorage.setItem('projectrai_token', 'e2e-access-token')
    localStorage.setItem('projectrai_org', JSON.stringify({ id: 'org-a', name: 'Tenant A', slug: 'tenant-a' }))
    localStorage.setItem('projectrai_project', JSON.stringify({
      id: 'project-a', organization_id: 'org-a', name: 'Release Project', slug: 'release-project',
    }))
  })

  await page.goto('/organizations/org-a/projects/project-a/agents/new')
  await page.getByPlaceholder('My Agent').fill(agent.name)
  await page.locator('select').first().selectOption(credential.id)
  await page.getByRole('button', { name: 'Create Agent' }).click()

  await expect(page).toHaveURL(/\/agents\/agent-a\/playground$/)
  await page.getByPlaceholder('Type your message...').fill('Run release gate')
  await page.getByPlaceholder('Type your message...').press('Enter')
  await expect(page.getByText('ProjectRAI release gate passed')).toBeVisible()

  await page.reload()
  await expect(page.getByText('ProjectRAI release gate passed')).toBeVisible()

  await page.goto('/organizations/org-a/projects/project-a/api-keys')
  await page.getByRole('button', { name: 'Create Key' }).first().click()
  await page.getByPlaceholder('Key name').fill('Release key')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.getByText('rai_live_e2e_deterministic-secret')).toBeVisible()
})

test('returns not found for a foreign project and does not leak tenant data', async ({ page }) => {
  await installDeterministicApi(page)
  await page.addInitScript(() => localStorage.setItem('projectrai_token', 'e2e-access-token'))

  const response = await page.request.get('/core/projects/project-b', {
    headers: { Authorization: 'Bearer e2e-access-token' },
  })
  expect(response.status()).toBe(404)
  expect(await response.json()).toMatchObject({ success: false, message: 'Resource not found' })

  await page.goto('/organizations/org-a/projects/project-b')
  await expect(page.getByText('Dashboard unavailable')).toBeVisible()
  await expect(page.getByText('Tenant B secret')).toHaveCount(0)
})
