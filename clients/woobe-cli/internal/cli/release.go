package cli

func (a *App) releaseCommands() {
	for _, op := range []Operation{
		{Command: "project agent release list", Method: "GET", Path: "/ai/agents/{agent_id}/releases", Scope: "project", Body: false},
		{Command: "project agent release create", Method: "POST", Path: "/ai/agents/{agent_id}/releases", Scope: "project", Body: true},
		{Command: "project agent release get", Method: "GET", Path: "/ai/agents/{agent_id}/releases/{release_id}", Scope: "project", Body: false},
		{Command: "project agent release delete", Method: "DELETE", Path: "/ai/agents/{agent_id}/releases/{release_id}", Scope: "project", Body: false},
		{Command: "project agent release test", Method: "POST", Path: "/ai/agents/{agent_id}/release-tests", Scope: "project", Body: true, Effect: "execution"},
		{Command: "project agent release run-test", Method: "POST", Path: "/ai/agents/{agent_id}/release-tests/run", Scope: "project", Body: true, Effect: "execution"},
		{Command: "project agent release tests", Method: "GET", Path: "/ai/agents/{agent_id}/releases/{release_id}/tests", Scope: "project", Body: false},
		{Command: "project agent release activations", Method: "GET", Path: "/ai/agents/{agent_id}/release-activations", Scope: "project", Body: false},
		{Command: "project agent environment list", Method: "GET", Path: "/ai/agents/{agent_id}/runtime-environments", Scope: "project", Body: false},
		{Command: "project agent environment update", Method: "PATCH", Path: "/ai/agents/{agent_id}/runtime-environments/{environment}", Scope: "project", Body: true},
		{Command: "project agent release promote", Method: "POST", Path: "/ai/agents/{agent_id}/releases/{release_id}/promote", Scope: "project", Body: true, Effect: "publication"},
		{Command: "project agent release rollback", Method: "POST", Path: "/ai/agents/{agent_id}/releases/{release_id}/rollback", Scope: "project", Body: true, Effect: "publication"},
	} {
		a.register(op)
	}
}
