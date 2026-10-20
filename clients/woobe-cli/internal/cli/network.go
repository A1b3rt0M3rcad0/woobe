package cli

func (a *App) networkCommands() {
	for _, op := range []Operation{
		{Command: "project network list", Method: "GET", Path: "/network/projects/{project_id}/networks", Scope: "project", Body: false, QueryScope: ""},
		{Command: "project network create", Method: "POST", Path: "/network/projects/{project_id}/networks", Scope: "project", Body: true},
		{Command: "project network get", Method: "GET", Path: "/network/projects/{project_id}/networks/{network_id}", Scope: "project", Body: false},
		{Command: "project network update", Method: "PATCH", Path: "/network/projects/{project_id}/networks/{network_id}", Scope: "project", Body: true},
		{Command: "project network draft update", Method: "PATCH", Path: "/network/{network_id}/draft", Scope: "project", Body: true},
		{Command: "project network promotion preview", Method: "POST", Path: "/network/{network_id}/promotions/preview", Scope: "project", Body: true},
		{Command: "project network promotion create", Method: "POST", Path: "/network/{network_id}/promotions", Scope: "project", Body: true, Effect: "publication"},
		{Command: "project network version list", Method: "GET", Path: "/network/{network_id}/versions", Scope: "project", Body: false, QueryScope: "project_id"},
		{Command: "project network management versions", Method: "GET", Path: "/network/{network_id}/management/versions", Scope: "project", Body: false},
		{Command: "project network management external-context", Method: "GET", Path: "/network/{network_id}/management/external-context-contract", Scope: "project", Body: false},
		{Command: "project network activation list", Method: "GET", Path: "/network/{network_id}/management/activations", Scope: "project", Body: false},
		{Command: "project network activation create", Method: "POST", Path: "/network/{network_id}/production/activations", Scope: "project", Body: true, Effect: "publication"},
		{Command: "project network rollback", Method: "POST", Path: "/network/{network_id}/rollback", Scope: "project", Body: true, Effect: "publication"},
		{Command: "project network environment list", Method: "GET", Path: "/network/{network_id}/runtime-environments", Scope: "project", Body: false},
		{Command: "project network environment update", Method: "PATCH", Path: "/network/{network_id}/runtime-environments/{environment}", Scope: "project", Body: true},
		{Command: "project network session list", Method: "GET", Path: "/network/{network_id}/sessions", Scope: "project", Body: false},
		{Command: "project network session create", Method: "POST", Path: "/network/{network_id}/sessions", Scope: "project", Body: true},
		{Command: "project network session messages", Method: "GET", Path: "/network/{network_id}/sessions/{session_id}/messages", Scope: "project", Body: false},
		{Command: "project network session reset-context", Method: "POST", Path: "/network/{network_id}/sessions/{session_id}/reset-context", Scope: "project", Body: true, Effect: "execution"},
	} {
		a.register(op)
	}
}
