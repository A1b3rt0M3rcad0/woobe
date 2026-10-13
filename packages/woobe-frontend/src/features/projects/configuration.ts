import { del, get, post, put } from '@/lib/api/client'
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
    environments: Array.from(new Set([...(existing?.environments ?? []), environment])),
    field_paths: Array.from(new Set([...(existing?.field_paths ?? []), row.field_path])),
    expected_revision: existing?.revision ?? 0 })
}
export function revokeConfigurationUse(project: string, policy: ConfigurationUsePolicy) {
  return del(`${configurationPath(project)}/use-policies/${policy.id}`, { params: { expected_revision: policy.revision } })
}
export function configurationUsage(project: string, key: string, offset = 0) {
  return get<ConfigurationUsage>(`${configurationPath(project)}/keys/${key}/usage`, { params: { offset, limit: 50 } })
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
