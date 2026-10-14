import { expect, type Page, type Route } from '@playwright/test'
import authorityFixture from './authority-categories.json'

export const now = '2026-06-20T12:00:00Z'
export const user = { id: 'user-a', email: 'owner-a@example.test', status: 'active' }
export const workspace = {
  id: 'workspace-a', name: 'Woobe Test Workspace', slug: 'woobe-test', status: 'active',
  membership_role: 'owner', can_manage_workspace: true, accessible_project_count: 1,
  access_mode: 'implicit_owner',
}
export const project = {
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
export const networks = [
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

export const overview = {
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

export async function respond(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(status < 400
      ? { success: true, message: 'ok', data }
      : { success: false, message: 'Resource not found', data: null }),
  })
}

export async function installApi(page: Page, options?: { freshCore?: boolean; asacAgent?: boolean; productionError?: boolean; runtimeEnabled?: boolean; detailsError?: boolean }) {
  const freshCore = options?.freshCore ?? false

  await page.route('**/*', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    if (path === '/runtime-config.js') {
      await route.continue()
      return
    }
    const prefixes = ['/identity', '/core', '/ai', '/runtime', '/observability', '/knowledge', '/tools', '/network', '/metering', '/projects']
    if (!prefixes.some((prefix) => path.startsWith(prefix))) {
      await route.continue()
      return
    }

    if (options?.asacAgent && path === '/ai/agents') {
      await respond(route, [productionAgent])
    } else if (options?.asacAgent && path === `/ai/agents/${productionAgent.id}`) {
      await respond(route, productionAgent)
    } else if (options?.asacAgent && path === `/ai/agents/${productionAgent.id}/runtime-environments`) {
      await respond(route, { draft: { enabled: true }, staging: { enabled: true }, production: { enabled: options.runtimeEnabled ?? true } })
    } else if (options?.asacAgent && path.endsWith('/asac/current')) {
      const environment = new URL(request.url()).searchParams.get('environment')
      await respond(route, { schema_version: '1.0', resource_id: productionAgent.id, kind: 'Agent', environment,
        snapshot_id: environment === 'production' ? selectedRelease.id : 'staging-snapshot', environment_generation: 1,
        selection_authority: environment === 'production' ? 'asac' : 'legacy', remote_status: 'verified', complete: true },
        options.productionError && environment === 'production' ? 500 : 200)
    } else if (options?.asacAgent && path === `/ai/agents/${productionAgent.id}/releases`) {
      await respond(route, [selectedRelease]) // No catalog row has status=production.
    } else if (options?.asacAgent && path.startsWith(`/ai/agents/${productionAgent.id}/releases/`)) {
      await respond(route, path.endsWith(selectedRelease.id) ? selectedRelease : { ...selectedRelease, id: 'staging-snapshot', version: 'staging', status: 'staging', snapshot_kind: 'staging' }, options.detailsError ? 403 : 200)
    } else if (options?.asacAgent && path === `/ai/agents/${productionAgent.id}/release-activations`) {
      await respond(route, [{ id: 'first', project_id: project.id, agent_id: productionAgent.id, release_id: selectedRelease.id,
        previous_release_id: null, action: 'reactivate', created_at: now }])
    } else if (options?.asacAgent && path === '/ai/context-managers') {
      await respond(route, [{ name: 'stdcm', display_name: 'Standard', config_schema: { type: 'object', properties: {} } }])
    } else if (options?.asacAgent && path === '/identity/access/me') {
      await respond(route, { permissions: [...authorityFixture.permissions.workspace, ...authorityFixture.permissions.project], conditions: {} })
    } else if (path === '/identity/instance/status') {
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

export async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('you@company.com').fill(user.email)
  await page.getByPlaceholder('Enter your password').fill('ReleaseGate123!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/workspaces\/workspace-a\/projects\/project-a|\/dashboard/)
}

export const productionAgent = {
  id: 'agent-asac', project_id: project.id, name: 'ASaC Production Agent', description: 'Selection UI acceptance',
  status: 'active', provider: 'custom', model: 'mutable-draft-model', session_mode: 'stateful', revision: 1,
  created_at: now, updated_at: now,
}
export const selectedRelease = {
  id: 'selected-release', project_id: project.id, agent_id: productionAgent.id, name: productionAgent.name,
  version: '1.2.0', status: 'released', snapshot_kind: 'release', provider: 'custom', model: 'frozen-release-model',
  session_mode: 'stateless', runtime_config: {}, created_at: now,
}
