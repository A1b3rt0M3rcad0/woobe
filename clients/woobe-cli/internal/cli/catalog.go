package cli

func (a *App) catalogCommands() {
	for _, op := range []Operation{
		{Command: "project provider-model list", Method: "GET", Path: "/ai/provider-models", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project provider-model create", Method: "POST", Path: "/ai/provider-models", Scope: "project", Body: true},
		{Command: "project provider-model get", Method: "GET", Path: "/ai/provider-models/{provider_model_id}", Scope: "project", Body: false},
		{Command: "project provider-model update", Method: "PATCH", Path: "/ai/provider-models/{provider_model_id}", Scope: "project", Body: true},
		{Command: "project provider-model usage", Method: "GET", Path: "/ai/provider-models/{provider_model_id}/usage", Scope: "project", Body: false},
		{Command: "project provider-credential list", Method: "GET", Path: "/ai/credentials", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project provider-credential create", Method: "POST", Path: "/ai/credentials", Scope: "project", Body: true},
		{Command: "project provider-credential update", Method: "PATCH", Path: "/ai/credentials/{credential_id}", Scope: "project", Body: true},
		{Command: "project provider-credential rotate", Method: "POST", Path: "/ai/credentials/{credential_id}/rotate", Scope: "project", Body: true},
		{Command: "project provider-credential revoke", Method: "POST", Path: "/ai/credentials/{credential_id}/revoke", Scope: "project", Body: false},
		{Command: "project provider-credential usage", Method: "GET", Path: "/ai/credentials/{credential_id}/usage", Scope: "project", Body: false},
		{Command: "project catalog context-assemblers", Method: "GET", Path: "/ai/context-assemblers", Scope: "project", Body: false},
		{Command: "project catalog execution-strategies", Method: "GET", Path: "/ai/execution-strategies", Scope: "project", Body: false},
		{Command: "project catalog knowledge-strategies", Method: "GET", Path: "/ai/knowledge-strategies", Scope: "project", Body: false},
		{Command: "project catalog rag-strategies", Method: "GET", Path: "/ai/rag-strategies", Scope: "project", Body: false},
	} {
		a.register(op)
	}
}
