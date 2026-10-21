package cli

func (a *App) toolCommands() {
	for _, op := range []Operation{
		{Command: "project tool list", Method: "GET", Path: "/tools/tools", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project tool create", Method: "POST", Path: "/tools/tools", Scope: "project", Body: true},
		{Command: "project tool update", Method: "PATCH", Path: "/tools/tools/{tool_id}", Scope: "project", Body: true},
		{Command: "project tool delete", Method: "DELETE", Path: "/tools/tools/{tool_id}", Scope: "project", Body: false},
		{Command: "project tool status", Method: "PATCH", Path: "/tools/tools/{tool_id}/status", Scope: "project", Body: true},
		{Command: "project tool usage-impact", Method: "GET", Path: "/tools/tools/{tool_id}/usage-impact", Scope: "project", Body: false},
		{Command: "project agent tool list", Method: "GET", Path: "/tools/agents/{agent_id}/tools", Scope: "project", Body: false},
		{Command: "project tool test", Method: "POST", Path: "/tools/tools/test", Scope: "project", Body: true, Effect: "execution"},
		{Command: "project tool execute", Method: "POST", Path: "/tools/tools/execute", Scope: "project", Body: true, Effect: "execution"},
		{Command: "project tool mcp discover", Method: "POST", Path: "/tools/mcp/discover", Scope: "project", Body: true},
		{Command: "project tool mcp refresh", Method: "POST", Path: "/tools/mcp/refresh", Scope: "project", Body: true},
		{Command: "project tool mcp set", Method: "PATCH", Path: "/tools/mcp/permissions", Scope: "project", Body: true},
		{Command: "project tool mcp bulk", Method: "POST", Path: "/tools/mcp/permissions/bulk", Scope: "project", Body: true},
		{Command: "project tool mcp oauth start", Method: "POST", Path: "/tools/mcp/oauth/start", Scope: "project", Body: true},
		{Command: "project tool mcp oauth complete", Method: "POST", Path: "/tools/mcp/oauth/complete", Scope: "project", Body: true},
		{Command: "project tool mcp oauth device-start", Method: "POST", Path: "/tools/mcp/oauth/device/start", Scope: "project", Body: true},
		{Command: "project tool mcp oauth device-poll", Method: "POST", Path: "/tools/mcp/oauth/device/poll", Scope: "project", Body: true},
		{Command: "project tool mcp oauth status", Method: "POST", Path: "/tools/mcp/oauth/status", Scope: "project", Body: true},
		{Command: "project tool mcp oauth disconnect", Method: "POST", Path: "/tools/mcp/oauth/disconnect", Scope: "project", Body: true},
	} {
		a.register(op)
	}
}
