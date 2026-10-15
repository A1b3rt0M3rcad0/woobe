import { expect, type Page, type Route } from '@playwright/test'
import authorityFixture from './authority-categories.json'

import { now, user, workspace, project, networks, overview, productionAgent, selectedRelease } from './control-plane-data'
export { now, user, workspace, project, networks, overview, productionAgent, selectedRelease } from './control-plane-data'

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
    if (request.isNavigationRequest() || path === '/runtime-config.js') {
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
      await respond(route, [{ name: 'stdcm', display_name: 'Standard', description: 'Standard context materialization.', behavior: 'Uses the configured context policy.', recommended_for: [], capabilities: [], limitations: [], configuration: '', is_default: true, config_schema: { type: 'object', properties: {} } }])
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
    } else if (path === '/identity/auth/csrf') {
      await respond(route, { csrf: 'csrf-test' })
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
    } else if (path === `/core/projects/${project.id}/configuration/summary`) {
      await respond(route, { environment: new URL(request.url()).searchParams.get('environment'),
        state: 'unknown', complete: false, scope: 'current_selections', checked_at: now,
        inspected_target_count: 0, unselected_target_count: 0, affected_target_count: 0,
        blocked_key_count: 0, missing_key_count: 0, required_key_count: 0, affected_consumer_count: 0 })
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
  // /dashboard still resolves Workspace/Project context and can close an opened
  // mobile drawer when it redirects. Interact only after the destination loads.
  await expect(page).toHaveURL(/\/workspaces\/workspace-a\/projects\/project-a(?:\/|$)/)
}
