package cli

func (a *App) agentCommands() {
	for _, op := range []Operation{
		{Command: "project agent list", Method: "GET", Path: "/ai/agents", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project agent create", Method: "POST", Path: "/ai/agents", Scope: "project", Body: true},
		{Command: "project agent get", Method: "GET", Path: "/ai/agents/{agent_id}", Scope: "project", Body: false},
		{Command: "project agent delete", Method: "DELETE", Path: "/ai/agents/{agent_id}", Scope: "project", Body: false, Effect: "deletion"},
		{Command: "project agent update", Method: "PATCH", Path: "/ai/agents/{agent_id}", Scope: "project", Body: true},
		{Command: "project agent prompt list", Method: "GET", Path: "/ai/agents/{agent_id}/prompts", Scope: "project", Body: false},
		{Command: "project agent prompt create", Method: "POST", Path: "/ai/agents/{agent_id}/prompts", Scope: "project", Body: true},
		{Command: "project agent prompt get", Method: "GET", Path: "/ai/agents/{agent_id}/prompts/{version_id}", Scope: "project", Body: false},
		{Command: "project agent contract list", Method: "GET", Path: "/ai/agents/{agent_id}/contracts", Scope: "project", Body: false},
		{Command: "project agent contract create", Method: "POST", Path: "/ai/agents/{agent_id}/contracts", Scope: "project", Body: true},
		{Command: "project agent contract get", Method: "GET", Path: "/ai/agents/{agent_id}/contracts/{contract_id}", Scope: "project", Body: false},
		{Command: "project agent contract update", Method: "PATCH", Path: "/ai/agents/{agent_id}/contracts/{contract_id}", Scope: "project", Body: true},
		{Command: "project agent model-config list", Method: "GET", Path: "/ai/agents/{agent_id}/model-configs", Scope: "project", Body: false},
		{Command: "project agent model-config create", Method: "POST", Path: "/ai/agents/{agent_id}/model-configs", Scope: "project", Body: true},
		{Command: "project agent model-config get", Method: "GET", Path: "/ai/agents/{agent_id}/model-configs/{config_id}", Scope: "project", Body: false},
	} {
		a.register(op)
	}
}
