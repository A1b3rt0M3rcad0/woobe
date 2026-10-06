import { get, post } from '@/lib/api/client'

export interface ProjectGrant {
  project_id: string
  permissions: string[]
  conditions?: Record<string, string[]>
}

export interface ControlKey {
  id: string
  name: string
  description: string | null
  key_prefix: string
  status: string
  permissions: string[]
  project_grants: ProjectGrant[]
  on_project_create_permissions: string[]
  expires_at: string | null
  last_used_at?: string | null
  created_at: string
  etag: string
}

export interface IssuedControlKey extends ControlKey {
  key: string
}

export interface CreateControlKey {
  name: string
  description: string | null
  permissions: string[]
  project_grants: ProjectGrant[]
  on_project_create_permissions: string[]
  expires_at: string | null
}

export interface PermissionCatalog {
  permissions: { workspace: string[]; project: string[] }
}

export interface EffectiveAccess {
  permissions: string[]
  conditions: Record<string, string[]>
}

const path = (workspaceId: string) =>
  `/core/workspaces/${workspaceId}/control-keys`

export function listControlKeys(workspaceId: string) {
  return get<ControlKey[]>(path(workspaceId), { sensitive: true })
}

export function getPermissionCatalog() {
  return get<PermissionCatalog>('/identity/permissions')
}

export function getEffectiveAccess(workspaceId: string, projectId?: string) {
  return get<EffectiveAccess>('/identity/access/me', {
    params: { workspace_id: workspaceId, project_id: projectId },
  })
}

// Issued secrets go directly to the one-time view, never a query/mutation cache.
export function createControlKey(
  workspaceId: string,
  body: CreateControlKey,
  idempotencyKey: string,
) {
  return post<IssuedControlKey>(path(workspaceId), body, {
    sensitive: true,
    headers: { 'Idempotency-Key': idempotencyKey },
  })
}

export function rotateControlKey(
  workspaceId: string,
  key: ControlKey,
  idempotencyKey: string,
) {
  return post<IssuedControlKey>(
    `${path(workspaceId)}/${key.id}/rotate`,
    {},
    {
      sensitive: true,
      headers: { 'If-Match': key.etag, 'Idempotency-Key': idempotencyKey },
    },
  )
}

export function revokeControlKey(workspaceId: string, key: ControlKey) {
  return post<ControlKey>(`${path(workspaceId)}/${key.id}/revoke`, undefined, {
    sensitive: true,
    headers: { 'If-Match': key.etag },
  })
}
