package cli

func (a *App) permissionCommands() {
	for _, op := range []Operation{
		{Command: "permission list", Method: "GET", Path: "/identity/permissions", Scope: "workspace", Body: false, Status: "proposed"},
		{Command: "permission effective", Method: "GET", Path: "/identity/access/me", Scope: "workspace", Body: false, Status: "proposed"},
		{Command: "permission check", Method: "POST", Path: "/identity/access/check", Scope: "workspace", Body: true, Status: "proposed"},
		{Command: "permission explain", Method: "POST", Path: "/identity/access/check", Scope: "workspace", Body: true, Status: "proposed"},
		{Command: "workspace authority audit", Method: "GET", Path: "/identity/workspaces/{workspace_id}/authority-audit", Scope: "workspace", Status: "proposed"},
		{Command: "workspace authority category list", Method: "GET", Path: "/identity/workspaces/{workspace_id}/authority-categories", Scope: "workspace", Body: false, Status: "proposed"},
		{Command: "workspace authority category get", Method: "GET", Path: "/identity/workspaces/{workspace_id}/authority-categories/{category_id}", Scope: "workspace", Body: false, Status: "proposed"},
		{Command: "workspace authority category create", Method: "POST", Path: "/identity/workspaces/{workspace_id}/authority-categories", Scope: "workspace", Body: true, Status: "proposed"},
		{Command: "workspace authority category update", Method: "PATCH", Path: "/identity/workspaces/{workspace_id}/authority-categories/{category_id}", Scope: "workspace", Body: true, Status: "proposed"},
		{Command: "workspace authority category clone", Method: "POST", Path: "/identity/workspaces/{workspace_id}/authority-categories/{category_id}/clone", Scope: "workspace", Body: true, Status: "proposed"},
		{Command: "workspace authority category history", Method: "GET", Path: "/identity/workspaces/{workspace_id}/authority-categories/{category_id}/versions", Scope: "workspace", Body: false, Status: "proposed"},
		{Command: "workspace authority category archive", Method: "POST", Path: "/identity/workspaces/{workspace_id}/authority-categories/{category_id}/archive", Scope: "workspace", Body: true, Status: "proposed"},
		{Command: "workspace authority category delete", Method: "DELETE", Path: "/identity/workspaces/{workspace_id}/authority-categories/{category_id}", Scope: "workspace", Body: false, Status: "proposed"},
	} {
		a.register(op)
	}
	a.categoryDiffCommand()
}
