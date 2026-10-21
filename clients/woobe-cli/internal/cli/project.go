package cli

func (a *App) projectCommands() {
	for _, op := range []Operation{
		{Command: "project agent git-attestation get", Method: "GET", Path: "/projects/{project_id}/agents/{resource_id}/asac/git-attestations/{attestation_id}", Scope: "project", Permission: "agent:read", Status: "proposed"},
		{Command: "project agent git-attestation create", Method: "POST", Path: "/projects/{project_id}/agents/{resource_id}/asac/git-attestations", Scope: "project", Permission: "agent:version", Status: "proposed", Body: true},
		{Command: "project network git-attestation get", Method: "GET", Path: "/projects/{project_id}/networks/{resource_id}/asac/git-attestations/{attestation_id}", Scope: "project", Permission: "network:read", Status: "proposed"},
		{Command: "project network git-attestation create", Method: "POST", Path: "/projects/{project_id}/networks/{resource_id}/asac/git-attestations", Scope: "project", Permission: "network:version", Status: "proposed", Body: true},
		{Command: "project agent signed-receipt get", Method: "GET", Path: "/projects/{project_id}/agents/{resource_id}/asac/signed-receipts/{category}/{receipt_id}", Scope: "project", Permission: "agent:read", Status: "proposed"},
		{Command: "project network signed-receipt get", Method: "GET", Path: "/projects/{project_id}/networks/{resource_id}/asac/signed-receipts/{category}/{receipt_id}", Scope: "project", Permission: "network:read", Status: "proposed"},
		{Command: "project lifecycle show", Method: "GET", Path: "/core/projects/{project_id}/lifecycle-policy", Scope: "project", Permission: "project:read", Status: "proposed"},
		{Command: "project lifecycle update", Method: "PUT", Path: "/core/projects/{project_id}/lifecycle-policy", Scope: "project", Permission: "project:access:write", Status: "proposed", Body: true},
		{Command: "project lifecycle operation", Method: "GET", Path: "/core/projects/{project_id}/lifecycle-policy/operations/{operation_id}", Scope: "project", Permission: "project:read", Status: "proposed"},
		{Command: "project list", Method: "GET", Path: "/core/projects", Scope: "project", Body: false, QueryScope: "workspace_id"},
		{Command: "project create", Method: "POST", Path: "/core/projects", Scope: "project", Body: true},
		{Command: "project get", Method: "GET", Path: "/core/projects/{resource_id}", Scope: "project", Body: false},
		{Command: "project update", Method: "PATCH", Path: "/core/projects/{resource_id}", Scope: "project", Body: true},
		{Command: "project overview", Method: "GET", Path: "/core/projects/{project_id}/overview", Scope: "project", Body: false},
		{Command: "project run list", Method: "GET", Path: "/core/projects/{project_id}/runs", Scope: "project", Body: false},
		{Command: "project member list", Method: "GET", Path: "/core/projects/{project_id}/members", Scope: "project", Body: false},
		{Command: "project member grant", Method: "POST", Path: "/core/projects/{project_id}/members", Scope: "project", Body: true},
		{Command: "project member revoke", Method: "DELETE", Path: "/core/projects/{project_id}/members/{user_id}", Scope: "project", Body: false},
		{Command: "project access grant", Method: "POST", Path: "/core/projects/{project_id}/access", Scope: "project", Body: true},
		{Command: "project access revoke", Method: "DELETE", Path: "/core/projects/{project_id}/access/{subject_type}/{subject_id}", Scope: "project", Body: false},
		{Command: "project env list", Method: "GET", Path: "/core/projects/{project_id}/environment-keys", Scope: "project", Body: false},
		{Command: "project env set", Method: "PUT", Path: "/core/projects/{project_id}/environment-keys/{key}", Scope: "project", Body: true},
		{Command: "project env unset", Method: "DELETE", Path: "/core/projects/{project_id}/environment-keys/{key}", Scope: "project", Body: false},
	} {
		a.register(op)
	}
}
