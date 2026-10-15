import type { Page } from '@playwright/test'
import { installApi, respond, productionAgent, project } from './control-plane'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

/** Local synthetic provider/configuration responses; no live provider calls. */
export async function installSetupFlow(page: Page, options: { connection?: boolean; model?: boolean; catalogError?: boolean; configurationDenied?: boolean; legacy?: boolean } = {}) {
  await installApi(page, { asacAgent: true })
  const credential = { id: 'setup-credential', project_id: project.id, provider: 'openrouter', name: 'Support gateway', status: 'active', authentication: { type: 'api_key', fields: { api_key: { source: 'project_environment', key: 'OPENROUTER_API_KEY' } } }, metadata: { base_url: 'https://openrouter.ai/api/v1' }, created_at: '2026-10-15T03:00:00Z' }
  if (options.legacy) credential.authentication.fields.api_key.source = 'legacy_configuration'
  const model = { id: 'setup-model', project_id: project.id, provider_credential_id: credential.id, provider: 'openrouter', name: 'Support model', model: 'synthetic/support-model', model_type: 'generation', status: 'active', metadata: {}, spec: {} }
  const key = { id: 'setup-key', key: 'OPENROUTER_API_KEY', kind: 'secret', description: 'Synthetic provider access', value_format: 'token', definition_revision: 1, origin: 'declared', material: 'missing', used_by_count: 0, values: {} }
  const state = { credential: options.connection || options.model ? credential : null as typeof credential | null, model: options.model ? model : null as typeof model | null, agent: { ...productionAgent }, keyDeclared: !!(options.connection || options.model), valueSaved: false, approved: false, catalogError: !!options.catalogError, failAgent: false, failModel: false, calls: [] as { path: string; method: string; body: any }[], modelWrites: 0, agentWrites: 0, providerRequests: 0 }
  await page.route('https://openrouter.ai/**', route => { state.providerRequests++; return route.abort() })
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname, method = request.method()
    if (request.isNavigationRequest() || !['/ai/', '/core/', '/runtime/', '/v1/'].some(prefix => path.startsWith(prefix))) return route.fallback()
    const body = method === 'GET' ? null : request.postDataJSON()
    state.calls.push({ path: path + url.search, method, body })
    if (path === '/ai/credentials') {
      if (method === 'POST') { state.credential = { ...credential, ...body }; return respond(route, state.credential, 201) }
      return respond(route, state.credential ? [state.credential] : [])
    }
    if (path === '/ai/provider-models') {
      if (method === 'POST') { state.modelWrites++; if (state.failModel) { state.failModel = false; return respond(route, null, 500) }; state.model = { ...model, ...body }; return respond(route, state.model, 201) }
      if (url.searchParams.has('available_for_credential_id')) return respond(route, [{ id: model.model, label: model.name, provider: 'openrouter', source: 'remote', raw: {}, model_type: 'generation' }], state.catalogError ? 500 : 200)
      return respond(route, state.model ? [state.model] : [])
    }
    if (path === '/ai/agents' && method === 'POST') { state.agentWrites++; if (state.failAgent) { state.failAgent = false; return respond(route, null, 500) }; state.agent = { ...productionAgent, ...body }; return respond(route, state.agent, 201) }
    if (path === `/ai/agents/${productionAgent.id}`) return respond(route, state.agent)
    if (path === `/core/projects/${project.id}/overview`) return respond(route, { ...projectOverviewFixture, environment: url.searchParams.get('environment') || 'all' })
    if (path === '/core/projects' && method === 'POST') return respond(route, { ...project, ...body }, 201)
    const config = `/core/projects/${project.id}/configuration`
    if (path === `${config}/keys`) {
      if (options.configurationDenied) return respond(route, null, 403)
      if (method === 'POST') { Object.assign(key, body); state.keyDeclared = true; return respond(route, key, 201) }
      return respond(route, { items: state.keyDeclared ? [{ ...key, material: state.valueSaved ? 'present' : 'missing', values: { draft: { configured: state.valueSaved, material: state.valueSaved ? 'present' : 'missing', revision: state.valueSaved ? 1 : 0, value_version: null } } }] : [], total: state.keyDeclared ? 1 : 0, offset: 0, limit: 50, has_next: false, environment: 'draft', permissions: { declare: true, 'value:write': true, 'value:clear': true, 'use-policy:write': true } })
    }
    if (path === `${config}/keys/${key.id}/values/draft` && method === 'PUT') { state.valueSaved = true; return respond(route, { configured: true, revision: 1 }) }
    if (path === `${config}/keys/${key.id}/usage`) return respond(route, { items: state.credential ? [{ consumer_kind: 'provider_credential', consumer_id: state.credential.id, definition_revision: '1', field_path: 'authentication.fields.api_key', required: true, destination: 'https://openrouter.ai/api/v1' }] : [], total: state.credential ? 1 : 0, offset: 0, limit: 50 })
    if (path === `${config}/keys/${key.id}/use-policies`) return respond(route, { items: state.approved ? [{ id: 'setup-policy', consumer_kind: 'provider_credential', consumer_scope: credential.id, destination: 'https://openrouter.ai/api/v1', field_paths: ['authentication.fields.api_key'], environments: ['draft'], revision: 1, revoked: false }] : [], total: state.approved ? 1 : 0 })
    if (path === `${config}/use-policies` && method === 'POST') { state.approved = true; return respond(route, { id: 'setup-policy' }, 201) }
    return route.fallback()
  })
  return state
}
