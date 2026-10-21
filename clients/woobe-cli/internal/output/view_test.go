package output

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func view(t *testing.T, options Options, value any, failure error, meta map[string]any) (string, map[string]any) {
	t.Helper()
	var b bytes.Buffer
	if err := WriteView(&b, options, Redact(value), nil, failure, meta); err != nil {
		t.Fatal(err)
	}
	var result map[string]any
	if options.Mode == "compact" {
		if err := json.Unmarshal(b.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
	}
	return b.String(), result
}

func TestConciseAgentListRetainsUsableIDsAndAllRows(t *testing.T) {
	id := "01a00d46-1ed7-71f7-99a4-aaa2cf81637c"
	data := map[string]any{"success": true, "data": []any{
		map[string]any{"id": id, "name": "Suporte", "status": "draft", "model": "gpt-4.1-mini", "project_id": "project", "system_prompt": strings.Repeat("large prompt ", 200), "temperature": 0.3, "settings": map[string]any{"private_token": "never-show"}},
		map[string]any{"id": "agent-2", "name": "Vendas", "status": "active", "model": "gpt-4.1"},
	}}
	text, _ := view(t, Options{Mode: "text", Command: "project agent list"}, data, nil, nil)
	if !strings.Contains(text, "NAME") || !strings.Contains(text, id) || !strings.Contains(text, "2 results.") || strings.Contains(text, "large prompt") || strings.Contains(text, "private_token") {
		t.Fatal(text)
	}
	compact, result := view(t, Options{Mode: "compact", Command: "project agent list"}, data, nil, nil)
	rows := result["data"].([]any)
	if len(rows) != 2 || len(rows[0].(map[string]any)) != 4 || rows[0].(map[string]any)["id"] != id || result["schema_version"] != nil {
		t.Fatal(compact)
	}
	_, wide := view(t, Options{Mode: "compact", Command: "project agent list", Wide: true}, data, nil, nil)
	if wide["data"].([]any)[0].(map[string]any)["system_prompt"] == nil || strings.Contains(compact, "never-show") {
		t.Fatal(wide)
	}
}

func TestConciseProjectionUsesDottedFieldsAndKeepsFalseZeroAndMissing(t *testing.T) {
	data := []any{map[string]any{"name": "Agent", "enabled": false, "revision": 0, "model": map[string]any{"name": "model"}, "api_key": "secret"}}
	_, v := view(t, Options{Mode: "compact", Fields: []string{"name", "enabled", "revision", "model.name", "missing", "api_key"}}, data, nil, nil)
	row := v["data"].([]any)[0].(map[string]any)
	if row["enabled"] != false || row["revision"] != float64(0) || row["model.name"] != "model" || row["missing"] != nil || row["api_key"] != "[REDACTED]" {
		t.Fatal(v)
	}
	for _, bad := range []string{"name..id", "", "name[0]", "model.*"} {
		if ValidateFields([]string{bad}) == nil {
			t.Fatal("accepted", bad)
		}
	}
}

func TestConcisePaginationPreservesUncertaintyAndPartialError(t *testing.T) {
	data := map[string]any{"success": true, "data": map[string]any{"items": []any{map[string]any{"id": "one", "name": "First"}}, "has_next": true, "next_cursor": "opaque-cursor"}}
	meta := map[string]any{"collection_complete": "not_verified", "traversal_complete": false, "complete": false}
	failure := &Error{Code: 10, DomainCode: "PARTIAL", Status: 503, Outcome: "unknown", RequestID: "request", Message: "connection lost"}
	text, _ := view(t, Options{Mode: "text"}, data, failure, meta)
	if !strings.Contains(text, "First") || !strings.Contains(text, "ERROR 10") || !strings.Contains(text, "unknown") || !strings.Contains(text, "opaque-cursor") || !strings.Contains(text, "not_verified") {
		t.Fatal(text)
	}
	_, v := view(t, Options{Mode: "compact"}, data, failure, meta)
	if len(v["data"].([]any)) != 1 || v["error"].(map[string]any)["write_outcome"] != "unknown" || v["meta"].(map[string]any)["complete"] != false {
		t.Fatal(v)
	}
}

func TestConciseAuthRetainsSelectionAndRemovesPermissionDump(t *testing.T) {
	projects := []any{map[string]any{"id": "p", "name": "ChatBot", "slug": "chatbot", "eligible": true, "status": "active", "permissions": []string{"agent:write", "agent:read"}}}
	data := map[string]any{"context": "woobe", "authenticated": true, "state": "authenticated", "project_id": "p", "workspace": map[string]any{"id": "w", "name": "My Workspace"}, "projects": projects}
	text, v := view(t, Options{Mode: "compact", Command: "auth login"}, data, nil, nil)
	if strings.Contains(text, "agent:write") || v["data"].(map[string]any)["project"].(map[string]any)["name"] != "ChatBot" {
		t.Fatal(text)
	}
	human, _ := view(t, Options{Mode: "text", Command: "auth login"}, data, nil, nil)
	if !strings.Contains(human, "Workspace: My Workspace") || !strings.Contains(human, "Project: ChatBot") || strings.Contains(human, "workspace.id") || strings.Contains(human, "agent:write") {
		t.Fatal(human)
	}
	data["state"], data["project_id"] = "project_selection_required", ""
	_, v = view(t, Options{Mode: "compact", Command: "auth login"}, data, nil, nil)
	if len(v["data"].(map[string]any)["available_projects"].([]any)) != 1 {
		t.Fatal(v)
	}
	human, _ = view(t, Options{Mode: "text", Command: "auth login"}, data, nil, nil)
	if !strings.Contains(human, "ChatBot") || !strings.Contains(human, "woobe context project select") {
		t.Fatal(human)
	}
	data["projects"] = []any{}
	_, v = view(t, Options{Mode: "compact", Command: "auth login"}, data, nil, nil)
	if v["data"].(map[string]any)["available_project_count"] != float64(0) {
		t.Fatal(v)
	}
}

func TestConciseDoctorDoesNotEmitOpenAPIAndKeepsFailures(t *testing.T) {
	data := map[string]any{"complete": false, "client_version": "1", "checks": map[string]any{
		"openapi":  map[string]any{"success": true, "data": map[string]any{"paths": map[string]any{"/huge-openapi-route": "schema"}}},
		"identity": map[string]any{"success": false, "error": map[string]any{"message": "unauthorized", "exit_code": 3}},
	}, "routes": []any{map[string]any{"command": "get", "advertised": true}, map[string]any{"command": "post", "advertised": false}}}
	text, _ := view(t, Options{Mode: "text", Command: "doctor"}, data, New(10, "diagnostic checks partially failed"), nil)
	if strings.Contains(text, "huge-openapi-route") || !strings.Contains(text, "unauthorized") || !strings.Contains(text, "not_evaluated") || !strings.Contains(text, "advertised_routes: 1") {
		t.Fatal(text)
	}
}

func TestConciseRecoveryAndUnknownResponsesAreNotDiscarded(t *testing.T) {
	for _, command := range []string{"schema", "server-schema", "manifest preflight", "package import", "package status"} {
		data := map[string]any{"id": "a", "retained_inventory": []any{"important-resource"}, "opaque_field": "keep"}
		text, _ := view(t, Options{Mode: "compact", Command: command}, data, nil, map[string]any{"complete": false})
		if !strings.Contains(text, "important-resource") || !strings.Contains(text, "opaque_field") || !strings.Contains(text, `"complete":false`) {
			t.Fatal(command, text)
		}
	}
	text, _ := view(t, Options{Mode: "compact"}, map[string]any{"unknown_dto": "keep"}, nil, nil)
	if !strings.Contains(text, "unknown_dto") {
		t.Fatal(text)
	}
}

func TestConciseIncompleteCollectionAndResourceItems(t *testing.T) {
	_, result := view(t, Options{Mode: "compact", Fields: []string{"id"}}, map[string]any{"items": []any{map[string]any{"id": "a"}}, "complete": false}, nil, nil)
	if result["meta"].(map[string]any)["complete"] != false {
		t.Fatal(result)
	}
	_, result = view(t, Options{Mode: "compact", Wide: true}, map[string]any{"id": "resource", "name": "Resource with items", "items": []any{"entry"}}, nil, nil)
	if result["data"].(map[string]any)["id"] != "resource" {
		t.Fatal(result)
	}
}

func TestConciseTextEscapesControlCharactersAndPreservesUnicode(t *testing.T) {
	text, _ := view(t, Options{Mode: "text"}, []any{map[string]any{"name": "A\nB\t\x1b[31m ação"}}, nil, nil)
	if strings.Contains(text, "\x1b") || !strings.Contains(text, "A B") || !strings.Contains(text, "ação") {
		t.Fatal(text)
	}
}

func TestConciseEmptySuccessHasTerminalConfirmation(t *testing.T) {
	text, _ := view(t, Options{Mode: "text"}, nil, nil, nil)
	if text != "Done.\n" {
		t.Fatal(text)
	}
}

func TestConciseDiscoveryKeepsActualPolicyAndInvocationFields(t *testing.T) {
	data := map[string]any{"command": "agent get", "availability": "observed", "body_required": false, "path_parameters": []any{"agent_id"}, "permission": "agent:read", "permission_source": "hint", "flags": []any{"verbose"}}
	_, result := view(t, Options{Mode: "compact", Command: "help"}, data, nil, nil)
	obj := result["data"].(map[string]any)
	if obj["availability"] != "observed" || obj["body_required"] != false || obj["path_parameters"] == nil || obj["permission_source"] != "hint" {
		t.Fatal(result)
	}
}

func TestConciseDryRunsAndNestedOperationalDataStayComplete(t *testing.T) {
	for _, data := range []any{
		map[string]any{"executed": false, "body": map[string]any{"name": "Created"}, "query": map[string]any{"project_id": "project"}},
		map[string]any{"kind": "ResourceProjection", "data": map[string]any{"id": "resource"}, "source_command": "agent get"},
		map[string]any{"agent_id": "agent", "daily_usage": []any{map[string]any{"cost": 12}}},
		map[string]any{"id": "network", "graph": map[string]any{"nodes": []any{"agent"}}},
		[]any{map[string]any{"id": "network", "graph": map[string]any{"nodes": []any{"agent"}}}},
	} {
		_, result := view(t, Options{Mode: "compact", Command: "request"}, data, nil, nil)
		expected, _ := normalized(data)
		a, _ := json.Marshal(result["data"])
		b, _ := json.Marshal(expected)
		if string(a) != string(b) {
			t.Fatal(string(a), string(b))
		}
	}
}

func TestDeploymentSummaryKeepsRecoveryAndCASWithoutBindingPayload(t *testing.T) {
	value := map[string]any{"deployment_id": "deployment", "operation_id": "original", "plan_id": "plan", "release_id": "release", "environment": "production", "generation_before": 4, "generation_after": 5, "state": "committed", "runtime_fingerprints": map[string]any{"credentials": map[string]any{"large": "payload"}}}
	summary := summarize("develop agent deployment", value).(map[string]any)
	for _, field := range []string{"deployment_id", "operation_id", "plan_id", "release_id", "environment", "generation_before", "generation_after", "state"} {
		if summary[field] != value[field] {
			t.Fatal("lost recovery or selection evidence", field)
		}
	}
	if _, ok := summary["runtime_fingerprints"]; ok {
		t.Fatal("unrequested binding payload in concise output")
	}
}

func TestOutputInitPreviewKeepsPathsAndExecutionStatus(t *testing.T) {
	data := map[string]any{"initialized": false, "executed": false, "reused": true, "config": "/project/.woobe-config", "root": "/project/.woobe", "context": "local", "agents": []string{"codex", "claude"}, "instructions": []string{"AGENTS.md", "CLAUDE.md"}, "lab": "/project/.woobe-lab", "files": []string{"verbose file detail"}}
	text, result := view(t, Options{Mode: "compact", Command: "init"}, data, nil, nil)
	projected := result["data"].(map[string]any)
	if projected["executed"] != false || projected["reused"] != true || projected["config"] != data["config"] || projected["lab"] != data["lab"] || len(projected["agents"].([]any)) != 2 || strings.Contains(text, "verbose file detail") {
		t.Fatal(text)
	}
}

func TestConfigurationBindingViewShowsSelectedRouteReferencesAndDryRunIntent(t *testing.T) {
	data := map[string]any{"target_kind": "tool", "target_id": "tool-id", "route_id": "orders", "revision": "revision",
		"authentication": map[string]any{"type": "bearer", "fields": map[string]any{"token": map[string]any{"source": "project_environment", "key": "ORDER_TOKEN"}}},
		"routes":         []any{map[string]any{"id": "unrelated", "authentication": map[string]any{"type": "none"}}}}
	text, _ := view(t, Options{Mode: "text", Command: "project configuration bind"}, data, nil, nil)
	if !strings.Contains(text, "orders") || !strings.Contains(text, "ORDER_TOKEN") || strings.Contains(text, "unrelated") || strings.Contains(text, "[REDACTED]") {
		t.Fatal(text)
	}
	preview := map[string]any{"method": "PUT", "path": "/configuration/bindings/tool/tool-id", "body": map[string]any{"route_id": "orders"}, "executed": false}
	text, _ = view(t, Options{Mode: "text", Command: "project configuration bind"}, preview, nil, nil)
	if !strings.Contains(text, "PUT") || !strings.Contains(text, "executed: false") || !strings.Contains(text, "orders") {
		t.Fatal(text)
	}
}
