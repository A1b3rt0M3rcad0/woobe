package cli

func (a *App) surfaceCommands() {
	for _, op := range []Operation{
		{Command: "project skill list", Method: "GET", Path: "/ai/projects/{project_id}/skills", Scope: "project", Body: false},
		{Command: "project skill create", Method: "POST", Path: "/ai/projects/{project_id}/skills", Scope: "project", Body: true},
		{Command: "project skill version list", Method: "GET", Path: "/ai/projects/{project_id}/skills/{skill_id}/versions", Scope: "project", Body: false},
		{Command: "project skill version create", Method: "POST", Path: "/ai/projects/{project_id}/skills/{skill_id}/versions", Scope: "project", Body: true},
		{Command: "project skill version get", Method: "GET", Path: "/ai/projects/{project_id}/skills/versions/{skill_version_id}", Scope: "project", Body: false},
		{Command: "project surface list", Method: "GET", Path: "/chat-surfaces/projects/{project_id}", Scope: "project", Body: false},
		{Command: "project surface create", Method: "POST", Path: "/chat-surfaces/projects/{project_id}", Scope: "project", Body: true},
		{Command: "project surface get", Method: "GET", Path: "/chat-surfaces/{surface_id}", Scope: "project", Body: false},
		{Command: "project surface update", Method: "PATCH", Path: "/chat-surfaces/{surface_id}", Scope: "project", Body: true},
		{Command: "project surface release", Method: "POST", Path: "/chat-surfaces/{surface_id}/release", Scope: "project", Body: true, Effect: "publication"},
		{Command: "project surface activate", Method: "POST", Path: "/chat-surfaces/{surface_id}/activate", Scope: "project", Body: true, Effect: "publication"},
		{Command: "project surface disable", Method: "POST", Path: "/chat-surfaces/{surface_id}/disable", Scope: "project", Body: false, Effect: "mutation"},
		{Command: "project surface archive", Method: "POST", Path: "/chat-surfaces/{surface_id}/archive", Scope: "project", Body: false, Effect: "mutation"},
		{Command: "project surface test-sessions", Method: "POST", Path: "/chat-surfaces/{surface_id}/test-sessions", Scope: "project", Body: true, Effect: "mutation"},
		{Command: "project surface sessions", Method: "GET", Path: "/chat-surfaces/{surface_id}/sessions", Scope: "project", Body: false},
		{Command: "project surface activity", Method: "GET", Path: "/chat-surfaces/{surface_id}/activity", Scope: "project", Body: false},
	} {
		a.register(op)
	}
}
