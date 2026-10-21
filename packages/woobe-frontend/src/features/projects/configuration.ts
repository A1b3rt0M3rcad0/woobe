import { del, get, patch, post, put } from '@/lib/api/client'
import type { ProjectEnvironment } from './types'

export type ConfigurationMaterial = 'missing' | 'present' | 'invalid_format' | 'revoked' | 'unavailable'
export interface ConfigurationKey {
  id: string
  key: string
  kind: 'value' | 'secret'
  description: string
  value_format: 'string' | 'token' | 'json' | 'pem' | 'url'
  definition_revision: number
  origin: string
  material: ConfigurationMaterial
  used_by_count: number
  approval?: { state: 'approved' | 'approval_required' | 'no_connections'; connection_count: number; approved_connection_count: number }
  values: Partial<Record<ProjectEnvironment, { configured: boolean; material: ConfigurationMaterial; revision: number; value_version: string | null }>>
}
export interface ConfigurationPage {
  items: ConfigurationKey[]
  total: number
  offset: number
  limit: number
  has_next: boolean
  environment: ProjectEnvironment
  permissions: Partial<Record<'declare' | 'value:write' | 'value:clear' | 'use-policy:write' | 'migrate', boolean>>
}
export const configurationPath = (project: string) => `/core/projects/${project}/configuration`
export function listConfiguration(project: string, environment: ProjectEnvironment, search = '', status = 'all', offset = 0) {
  return get<ConfigurationPage>(`${configurationPath(project)}/keys`, { params: { environment, search, status, offset, limit: 50 } })
}
export function declareConfiguration(project: string, declaration: Pick<ConfigurationKey, 'key' | 'kind' | 'description' | 'value_format'>) {
  return post<ConfigurationKey>(`${configurationPath(project)}/keys`, declaration)
}
export function updateConfiguration(project: string, key: ConfigurationKey, changes: Pick<ConfigurationKey, 'description' | 'value_format'>) {
  return patch<ConfigurationKey>(`${configurationPath(project)}/keys/${key.id}`,
    { ...changes, expected_revision: key.definition_revision })
}
export interface ConfigurationDeletionCheck {
  key_id: string
  definition_revision: number
  can_delete: boolean
  scope: 'all_environments'
  blockers: { retained_resources: boolean; legacy_binding: boolean; active_run: boolean }
}
export async function checkConfigurationDeletion(project: string, key: ConfigurationKey, environment: ProjectEnvironment) {
  const result = await get<ConfigurationDeletionCheck>(`${configurationPath(project)}/keys/${key.id}/deletion-check`, { params: { environment } })
  if (!result || result.key_id !== key.id || result.scope !== 'all_environments'
    || !Number.isSafeInteger(result.definition_revision) || result.definition_revision < 1
    || typeof result.can_delete !== 'boolean' || !result.blockers
    || ['retained_resources', 'legacy_binding', 'active_run'].some(name => typeof result.blockers[name as keyof typeof result.blockers] !== 'boolean')
    || result.can_delete !== !Object.values(result.blockers).some(Boolean)) {
    throw new Error('Configuration usage could not be verified.')
  }
  return result
}
export function deleteConfiguration(project: string, key: ConfigurationKey) {
  return del(`${configurationPath(project)}/keys/${key.id}`, { params: { expected_revision: key.definition_revision } })
}
export async function configurationKeyMetadata(project: string, key: ConfigurationKey, environment: ProjectEnvironment) {
  for (let offset = 0; ; offset += 50) {
    const page = await listConfiguration(project, environment, key.key, 'all', offset)
    if (!page || page.environment !== environment || !Array.isArray(page.items)
      || !page.permissions || typeof page.permissions !== 'object') throw new Error('Configuration environment could not be verified.')
    const item = page.items.find(candidate => candidate.id === key.id)
    if (item) return { item, permissions: page.permissions }
    if (!page.has_next) throw new Error('Configuration key is no longer available.')
  }
}
export function writeConfiguration(project: string, key: ConfigurationKey, environment: ProjectEnvironment, value: string) {
  // Direct sensitive request: never retain input in a mutation cache or logs.
  return put(`${configurationPath(project)}/keys/${key.id}/values/${environment}`,
    { value, expected_revision: key.values[environment]?.revision ?? 0 }, { sensitive: true })
}
export function clearConfiguration(project: string, key: ConfigurationKey, environment: ProjectEnvironment) {
  return del(`${configurationPath(project)}/keys/${key.id}/values/${environment}`,
    { params: { expected_revision: key.values[environment]?.revision ?? 0 }, sensitive: true })
}
export interface ConfigurationUsage {
  items: ConfigurationConsumer[]
  total: number; offset: number; limit: number
}
export interface ConfigurationConsumer {
  consumer_kind: 'provider_credential' | 'tool' | 'secret' | 'mcp_oauth'
  consumer_id: string; definition_revision: string; field_path: string; required: boolean; destination: string
  approval?: { state: 'approved' | 'approval_required' | 'destination_required'; policy: ConfigurationUsePolicy | null; update_policy: ConfigurationUsePolicy | null }
}
export interface ConfigurationUsePolicy {
  id: string; consumer_kind: string; consumer_scope: string; destination: string
  field_paths: string[]; environments: ProjectEnvironment[]; revision: number; revoked: boolean
}
export function listConfigurationPolicies(project: string, key: string, offset = 0) {
  return get<{ items: ConfigurationUsePolicy[]; total: number }>(`${configurationPath(project)}/keys/${key}/use-policies`, { params: { offset, limit: 50 } })
}
export function grantConfigurationUse(project: string, key: string, row: ConfigurationConsumer, environment: ProjectEnvironment, existing?: ConfigurationUsePolicy) {
  return post(`${configurationPath(project)}/use-policies`, { key_id: key, consumer_kind: row.consumer_kind,
    consumer_scope: row.consumer_id, destination: row.destination,
    environments: Array.from(new Set([...(existing?.revoked ? [] : existing?.environments ?? []), environment])),
    field_paths: Array.from(new Set([...(existing?.revoked ? [] : existing?.field_paths ?? []), row.field_path])),
    expected_revision: existing?.revision ?? 0 })
}
export function revokeConfigurationUse(project: string, policy: ConfigurationUsePolicy) {
  return del(`${configurationPath(project)}/use-policies/${policy.id}`, { params: { expected_revision: policy.revision } })
}
export function configurationUsage(project: string, key: string, offset = 0, environment: ProjectEnvironment = 'draft', consumer?: { kind: string; id: string }) {
  return get<ConfigurationUsage>(`${configurationPath(project)}/keys/${key}/usage`, { params: { offset, limit: 50, environment,
    ...(consumer ? { consumer_kind: consumer.kind, consumer_id: consumer.id } : {}) } })
}

export async function configurationKeyByName(project: string, name: string, environment: ProjectEnvironment) {
  for (let offset = 0; ; offset += 50) {
    const page = await listConfiguration(project, environment, name, 'all', offset)
    if (!page || page.environment !== environment || !Array.isArray(page.items) || !page.permissions) throw new Error('Configuration unavailable')
    const item = page.items.find(item => item.key === name)
    if (item) return { item, permissions: page.permissions }
    if (!page.has_next) throw new Error('Configuration key unavailable')
  }
}

export function writeConfigurationBatch(project: string, environment: ProjectEnvironment, keys: ConfigurationKey[], values: Record<string, string>, requestId: string) {
  return post(`${configurationPath(project)}/value-batches`, { request_id: requestId,
    operations: keys.filter(key => Object.prototype.hasOwnProperty.call(values, key.id) && values[key.id] !== '').map(key => ({
      key_id: key.id, environment, expected_revision: key.values[environment]?.revision ?? 0, value: values[key.id], clear: false,
    })) }, { sensitive: true })
}
export interface LegacyConfigurationBinding {
  id: string; key_id: string; key: string; source_kind: string; source_id: string; field_path: string
  revision: number; state: string; source: string; material: ConfigurationMaterial
}
export function listLegacyConfiguration(project: string, environment: ProjectEnvironment, offset = 0) {
  return get<{ items: LegacyConfigurationBinding[]; total: number }>(`${configurationPath(project)}/legacy-bindings`, { params: { environment, offset, limit: 50 } })
}
export async function convertLegacyConfiguration(project: string, environment: ProjectEnvironment, binding: LegacyConfigurationBinding) {
  let offset = 0
  let key: ConfigurationKey | undefined
  for (;;) {
    const page = await listConfiguration(project, environment, binding.key, 'all', offset)
    key = page.items.find(item => item.id === binding.key_id)
    if (key || !page.has_next) break
    offset += page.limit
  }
  if (!key) throw new Error('Reload the configuration declaration before converting it.')
  return post(`${configurationPath(project)}/legacy-bindings/${binding.id}/convert`, {
    environments: [environment], expected_revision: binding.revision,
    expected_values: { [environment]: key.values[environment]?.revision ?? 0 },
  })
}

export function testConfigurationConnection(project: string, kind: 'provider_credential' | 'tool', identifier: string, environment: ProjectEnvironment) {
  return post<{ state: string; initialized?: boolean; discovered_count?: number }>(`${configurationPath(project)}/tests/${kind}/${identifier}`, { environment })
}

export interface ConfigurationReadiness {
  environment: ProjectEnvironment
  state: 'ready' | 'ready_with_notices' | 'blocked' | 'unknown'
  required_key_count: number
  missing_key_count: number
  affected_consumer_count: number
  dependencies: { key: string; code: string | null; material: ConfigurationMaterial; required: boolean; external_validation: string; source: string }[]
  unresolved: { code: string; consumer_kind: string; consumer_id: string }[]
}
export async function getConfigurationReadiness(project: string, kind: 'agent' | 'network', target: string, environment: ProjectEnvironment, versionId?: string) {
  const result = await get<ConfigurationReadiness>(`${configurationPath(project)}/readiness/${kind}/${target}`, {
    params: { environment, ...(versionId ? { version_id: versionId } : {}) },
  })
  if (!result || result.environment !== environment || !['ready', 'ready_with_notices', 'blocked', 'unknown'].includes(result.state)
    || ![result.required_key_count, result.missing_key_count, result.affected_consumer_count].every(value => Number.isInteger(value) && value >= 0)
    || !Array.isArray(result.dependencies) || !Array.isArray(result.unresolved)
    || result.dependencies.some(item => !item || typeof item.key !== 'string' || typeof item.material !== 'string'
      || (item.code !== null && typeof item.code !== 'string'))) {
    throw new Error('Configuration readiness response is incomplete.')
  }
  return result
}

export function configurationReturnPath(value: string | null, projectId: string, origin: string): string | null {
  if (!value?.startsWith('/') || value.startsWith('//') || value.includes('\\')) return null
  try {
    const url = new URL(value, origin)
    const match = url.pathname.match(/^\/(?:workspaces\/[^/]+\/)?projects\/([^/]+)(?:\/(.*))?$/)
    if (url.origin !== origin || !match || match[1] !== projectId || (match[2] ?? '').startsWith('environments')) return null
    return url.pathname + url.search
  } catch { return null }
}

export interface ConfigurationSummary {
  environment: ProjectEnvironment
  state: ConfigurationReadiness['state']
  complete: boolean
  scope: 'current_selections' | 'current_selections_page'
  page_state?: ConfigurationReadiness['state']
  page_complete?: boolean
  has_next?: boolean
  next_cursor?: string | null
  limit?: number
  checked_at: string
  inspected_target_count: number
  unselected_target_count: number
  affected_target_count: number
  blocked_key_count: number
  missing_key_count: number
  required_key_count: number
  affected_consumer_count: number
}
export async function getConfigurationSummary(project: string, environment: ProjectEnvironment) {
  const result = await get<ConfigurationSummary>(`${configurationPath(project)}/summary`, { params: { environment } })
  if (!result || result.environment !== environment || !['current_selections', 'current_selections_page'].includes(result.scope)
    || !['ready', 'ready_with_notices', 'blocked', 'unknown'].includes(result.state)
    || typeof result.complete !== 'boolean' || typeof result.checked_at !== 'string'
    || (!result.complete && result.state !== 'unknown')
    || (result.scope === 'current_selections_page' && (result.state !== 'unknown' || result.complete))
    || ![result.inspected_target_count, result.unselected_target_count, result.affected_target_count,
      result.blocked_key_count, result.missing_key_count, result.required_key_count, result.affected_consumer_count]
      .every(value => Number.isSafeInteger(value) && value >= 0)) throw new Error('Configuration summary is incomplete.')
  return result
}
