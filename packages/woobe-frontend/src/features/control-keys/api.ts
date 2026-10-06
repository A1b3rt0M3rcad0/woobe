import { get, post } from '@/lib/api/client'

export interface ProjectGrant {
  project_id: string
  permissions: string[]
  conditions?: Record<string, string[]>
  category_id?: string
  category_revision?: number
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
  category_id?: string
  category_revision?: number
}

export interface AuthorityCategory {
  id: string
  name: string
  description: string | null
  scope: 'workspace' | 'project'
  revision: number
  permissions: string[]
  conditions: Record<string, string[]>
  system: boolean
  status: string
}

interface CategoryPage {
  items: AuthorityCategory[]
  system_categories: AuthorityCategory[]
  complete: boolean
  next_cursor: string | null
}

export async function listAuthorityCategories(
  workspaceId: string,
): Promise<AuthorityCategory[]> {
  const categories = new Map<string, AuthorityCategory>()
  const cursors = new Set<string>()
  let cursor: string | undefined
  while (true) {
    const page = await get<CategoryPage>(
      `/identity/workspaces/${workspaceId}/authority-categories`,
      { params: { limit: 200, cursor } },
    )
    for (const category of [...page.system_categories, ...page.items])
      categories.set(category.id, category)
    if (page.complete) return [...categories.values()]
    if (!page.next_cursor || cursors.has(page.next_cursor))
      throw new Error('Unable to finish loading access roles')
    cursor = page.next_cursor
    cursors.add(cursor)
  }
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
