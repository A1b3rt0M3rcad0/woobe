package cli

func (a *App) workspaceCommands() {
	for _, op := range []Operation{
		{Command: "workspace list", Method: "GET", Path: "/identity/workspaces", Scope: "workspace", Body: false},
		{Command: "workspace create", Method: "POST", Path: "/identity/workspaces", Scope: "workspace", Body: true},
		{Command: "workspace get", Method: "GET", Path: "/identity/workspaces/{workspace_id}", Scope: "workspace", Body: false},
		{Command: "workspace update", Method: "PATCH", Path: "/identity/workspaces/{workspace_id}", Scope: "workspace", Body: true},
		{Command: "workspace member list", Method: "GET", Path: "/identity/workspaces/{workspace_id}/members", Scope: "workspace", Body: false},
		{Command: "workspace member remove", Method: "DELETE", Path: "/identity/workspaces/{workspace_id}/members/{user_id}", Scope: "workspace", Body: false},
		{Command: "workspace invite list", Method: "GET", Path: "/identity/workspaces/{workspace_id}/invites", Scope: "workspace", Body: false},
		{Command: "workspace invite create", Method: "POST", Path: "/identity/workspaces/{workspace_id}/invites", Scope: "workspace", Body: true},
		{Command: "workspace invite cancel", Method: "DELETE", Path: "/identity/workspaces/{workspace_id}/invites/{invite_id}", Scope: "workspace", Body: false},
		{Command: "workspace project-access list", Method: "GET", Path: "/core/workspaces/{workspace_id}/project-access", Scope: "workspace", Body: false},
	} {
		a.register(op)
	}
}
