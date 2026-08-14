export interface User {
  id: string
  email: string
  status?: string
  created_at?: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface Workspace {
  id: string
  name: string
  slug: string
  status?: string
  created_at?: string | null
  membership_role?: 'owner' | 'admin' | 'member' | 'viewer'
  can_manage_workspace?: boolean
  accessible_project_count?: number
  access_mode?: 'implicit_owner' | 'assigned_projects'
}

export interface LoginResponse {
  token_type?: string
  expires_in?: number
  csrf?: string
  user: User
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface RegisterResponse extends LoginResponse {
  workspace: Workspace
}

export interface InstanceStatus {
  initialized: boolean
  edition: 'community'
  signup_mode: 'bootstrap' | 'open' | 'invite_only' | 'disabled'
  telemetry_enabled: boolean
  requires_existing_owner_bootstrap: boolean
}
