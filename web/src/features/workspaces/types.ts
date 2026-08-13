export interface Workspace {
  id: string
  name: string
  slug: string
  status?: string
  created_at?: string | null
  updated_at?: string | null
  can_manage?: boolean
}

export interface WorkspaceMember {
  user_id: string
  email: string
  status: string
  joined_at?: string | null
}

export interface WorkspaceInvite {
  id: string
  workspace_id: string
  email: string
  status: 'pending' | 'accepted' | 'expired' | 'revoked' | 'cancelled'
  expires_at: string
  created_at?: string | null
  project_count?: number
  project_ids?: string[]
}

export interface PendingWorkspaceInvite extends WorkspaceInvite {
  workspace_name: string
  workspace_slug: string
}

export interface CreateWorkspaceRequest {
  name: string
  slug: string
}

export interface UpdateWorkspaceRequest {
  name?: string
  slug?: string
}

export interface CreateWorkspaceInviteRequest {
  email: string
  workspace_id: string
  project_ids: string[]
}
