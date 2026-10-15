import type { Page } from '@playwright/test'
import type { ConfigurationDeletionCheck, ConfigurationPage } from '../../../packages/woobe-frontend/src/features/projects/configuration'
import type { ProjectEnvironment } from '../../../packages/woobe-frontend/src/features/projects/types'
import { project, respond } from '../fixtures/control-plane'

/** Metadata-only responses shared by the configuration modal review scenarios. */
export async function installConfigurationReviewApi(page: Page) {
  const keysPath = `/core/projects/${project.id}/configuration/keys`
  await page.route('**/configuration/keys**', async route => {
    const url = new URL(route.request().url())
    if (route.request().method() !== 'GET') return route.fallback()
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
