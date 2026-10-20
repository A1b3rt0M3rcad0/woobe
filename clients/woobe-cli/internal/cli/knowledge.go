package cli

func (a *App) knowledgeCommands() {
	for _, op := range []Operation{
		{Command: "project knowledge collection list", Method: "GET", Path: "/knowledge/collections", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project knowledge collection create", Method: "POST", Path: "/knowledge/collections", Scope: "project", Body: true},
		{Command: "project knowledge collection get", Method: "GET", Path: "/knowledge/collections/{collection_id}", Scope: "project", Body: false},
		{Command: "project knowledge collection update", Method: "PATCH", Path: "/knowledge/collections/{collection_id}", Scope: "project", Body: true},
		{Command: "project knowledge document list", Method: "GET", Path: "/knowledge/documents", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project knowledge document create", Method: "POST", Path: "/knowledge/documents", Scope: "project", Body: true},
		{Command: "project knowledge document get", Method: "GET", Path: "/knowledge/documents/{document_id}", Scope: "project", Body: false},
		{Command: "project knowledge document delete", Method: "DELETE", Path: "/knowledge/documents/{document_id}", Scope: "project", Body: false},
		{Command: "project knowledge search", Method: "POST", Path: "/knowledge/search", Scope: "project", Body: true},
		{Command: "project agent knowledge list", Method: "GET", Path: "/knowledge/agent-collections", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project agent knowledge bind", Method: "POST", Path: "/knowledge/agent-collections", Scope: "project", Body: true},
		{Command: "project agent knowledge unbind", Method: "DELETE", Path: "/knowledge/agent-collections/{link_id}", Scope: "project", Body: false},
		{Command: "project agent knowledge version-create", Method: "POST", Path: "/knowledge/agents/{agent_id}/knowledge-versions", Scope: "project", Body: true},
		{Command: "project agent knowledge version-list", Method: "GET", Path: "/knowledge/agents/{agent_id}/knowledge-versions", Scope: "project", Body: false},
		{Command: "project knowledge collection overview", Method: "GET", Path: "/agent/knowledge/collections/{collection_id}/overview", Scope: "project", Body: false},
		{Command: "project knowledge collection vector-preview", Method: "POST", Path: "/agent/knowledge/collections/{collection_id}/vector-preview", Scope: "project", Body: true},
		{Command: "project knowledge snapshot create", Method: "POST", Path: "/agent/knowledge/collections/{collection_id}/vector-snapshots", Scope: "project", Body: true},
		{Command: "project knowledge snapshot list", Method: "GET", Path: "/agent/knowledge/collections/{collection_id}/vector-snapshots", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project knowledge snapshot prepare", Status: "proposed", Summary: "Queue a structural Knowledge snapshot after remote configuration is ready", Details: "Requires the server-advertised preparation route. Supply environment and expected_build_config_hash in YAML. BUILDING is pending; poll snapshot get until READY. Does not activate an Agent or deployment.", Method: "POST", Path: "/agent/knowledge/vector-snapshots/{snapshot_id}/prepare", Scope: "project", Body: true},
		{Command: "project knowledge snapshot get", Method: "GET", Path: "/agent/knowledge/vector-snapshots/{snapshot_id}", Scope: "project", Body: false},
	} {
		a.register(op)
	}
}
