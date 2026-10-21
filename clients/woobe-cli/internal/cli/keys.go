package cli

func (a *App) keysCommands() {
	for _, op := range []Operation{
		{Command: "workspace control-key list", Method: "GET", Path: "/core/workspaces/{workspace_id}/control-keys", Scope: "workspace", Body: false, Status: "branch-dependent"},
		{Command: "workspace control-key create", Method: "POST", Path: "/core/workspaces/{workspace_id}/control-keys", Scope: "workspace", Body: true, Secret: true, Status: "branch-dependent"},
		{Command: "workspace control-key update", Method: "PATCH", Path: "/core/workspaces/{workspace_id}/control-keys/{control_key_id}", Scope: "workspace", Body: true, Status: "branch-dependent"},
		{Command: "workspace control-key rotate", Method: "POST", Path: "/core/workspaces/{workspace_id}/control-keys/{control_key_id}/rotate", Scope: "workspace", Body: false, Secret: true, Status: "branch-dependent"},
		{Command: "workspace control-key revoke", Method: "POST", Path: "/core/workspaces/{workspace_id}/control-keys/{control_key_id}/revoke", Scope: "workspace", Body: false, Secret: false, Status: "branch-dependent"},
		{Command: "project api-key list", Method: "GET", Path: "/core/projects/{project_id}/api-keys", Scope: "project", Body: false, Status: "observed"},
		{Command: "project api-key create", Method: "POST", Path: "/core/projects/{project_id}/api-keys", Scope: "project", Body: true, Secret: true, Status: "observed"},
		{Command: "project api-key update", Method: "PATCH", Path: "/core/projects/{project_id}/api-keys/{api_key_id}", Scope: "project", Body: true, Status: "observed"},
		{Command: "project api-key rotate", Method: "POST", Path: "/core/projects/{project_id}/api-keys/{api_key_id}/rotate", Scope: "project", Body: false, Secret: true, Status: "observed"},
		{Command: "project api-key revoke", Method: "POST", Path: "/core/projects/{project_id}/api-keys/{api_key_id}/revoke", Scope: "project", Body: false, Secret: false, Status: "observed"},
		{Command: "project surface access-key list", Method: "GET", Path: "/chat-surfaces/{surface_id}/access-keys", Scope: "project", Body: false, Status: "observed"},
		{Command: "project surface access-key create", Method: "POST", Path: "/chat-surfaces/{surface_id}/access-keys", Scope: "project", Body: true, Secret: true, Status: "observed"},
		{Command: "project surface access-key rotate", Method: "POST", Path: "/chat-surfaces/{surface_id}/access-keys/{api_key_id}/rotate", Scope: "project", Body: false, Secret: true, Status: "observed"},
		{Command: "project surface access-key revoke", Method: "POST", Path: "/chat-surfaces/{surface_id}/access-keys/{api_key_id}/revoke", Scope: "project", Body: false, Secret: false, Status: "observed"},
		{Command: "project runtime-key create", Method: "POST", Path: "/core/projects/{project_id}/runtime-keys", Scope: "project", Body: true, Secret: true},
	} {
		a.register(op)
	}
}
