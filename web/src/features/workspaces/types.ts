export interface WorkspaceDetail {
  id: string
  name: string
  slug: string
  status: string
  created_at: string | null
}

export interface Member {
  id: string
  user_id: string
  workspace_id: string
  email: string
  role: string
  status: string
  joined_at?: string | null
  access_mode: 'implicit_owner' | 'assigned_projects'
  project_access_count: number
}

export interface Invite {
  id: string
  workspace_id: string
  email: string
  role: string
  status: string
  expires_at: string | null
  accepted_at?: string | null
  created_at: string | null
  project_ids: string[]
  project_count: number
}

export interface PendingInvite extends Invite {
  workspace_name: string
  workspace_slug: string
}

export interface UpdateWorkspaceRequest {
  name?: string
  slug?: string
}

export interface CreateWorkspaceRequest {
  name: string
  slug: string
}

export interface CreateInviteRequest {
  email: string
  role: 'member' | 'admin'
  project_ids: string[]
}

export interface RemoveWorkspaceMemberResult {
  workspace_membership_removed: boolean
  project_accesses_removed: number
  pending_accesses_cancelled: number
}

export interface CancelWorkspaceInviteResult {
  invite_cancelled: boolean
  pending_accesses_cancelled: number
}
