import type { Page } from '@playwright/test'
import type { ConfigurationDeletionCheck, ConfigurationPage } from '../../../packages/woobe-frontend/src/features/projects/configuration'
import type { ProjectEnvironment } from '../../../packages/woobe-frontend/src/features/projects/types'
import { project, respond } from '../fixtures/control-plane'

/** Metadata-only responses shared by the configuration modal review scenarios. */
export async function installConfigurationReviewApi(page: Page) {
  const keysPath = `/core/projects/${project.id}/configuration/keys`
  let approved = false
  const policy = { id: 'policy-demo', consumer_kind: 'tool', consumer_scope: 'tool-demo', destination: 'https://example.test/support', field_paths: ['config.url'], environments: ['draft'], revision: 1, revoked: false }
  await page.route('**/configuration/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/use-policies') && route.request().method() === 'POST') { approved = true; return respond(route, policy) }
    if (url.pathname.endsWith('/use-policies/policy-demo') && route.request().method() === 'DELETE') { approved = false; return respond(route, {}) }
    if (route.request().method() !== 'GET') return route.fallback()
    if (url.pathname.endsWith('/config-demo/usage')) return respond(route, { items: [{ consumer_kind: 'tool', consumer_id: 'tool-demo', definition_revision: '1', field_path: 'config.url', required: true, destination: 'https://example.test/support', approval: { state: approved ? 'approved' : 'approval_required', policy: approved ? policy : null, update_policy: approved ? policy : null } }], total: 1, offset: 0, limit: 50 })
    if (url.pathname.endsWith('/config-demo/use-policies')) return respond(route, { items: approved ? [policy] : [], total: approved ? 1 : 0 })
    if (url.pathname === keysPath) {
      const environment = (url.searchParams.get('environment') ?? 'draft') as ProjectEnvironment
      return respond(route, {
        environment,
        items: [{ id: 'config-demo', key: 'SUPPORT_ENDPOINT', kind: 'value', description: 'Support endpoint', value_format: 'url', definition_revision: 1, origin: 'manual', material: 'present', used_by_count: 0,
          values: { [environment]: { configured: true, revision: 1, material: 'present', value_version: 'opaque-version' } } }],
        total: 1, offset: 0, limit: 50, has_next: false, permissions: { 'value:write': true, 'value:clear': true },
      } satisfies ConfigurationPage)
    }
    if (url.pathname === `${keysPath}/config-demo/deletion-check`) return respond(route, {
      key_id: 'config-demo', definition_revision: 1, scope: 'all_environments', can_delete: true,
      blockers: { retained_resources: false, legacy_binding: false, active_run: false },
    } satisfies ConfigurationDeletionCheck)
    return route.fallback()
  })
}
