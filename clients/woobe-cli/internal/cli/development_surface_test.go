package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestSurfaceCreatePushCASAndUnknownOutcomeCheckpoint(t *testing.T) {
	for _, scenario := range []string{"success", "stale", "unknown", "rejected"} {
		t.Run(scenario, func(t *testing.T) {
			t.Chdir(t.TempDir())
			t.Setenv("WOOBE_CONTROL_KEY", "test")
			revision := "2026-10-07T00:00:00Z"
			creates, patches := 0, 0
			remote := map[string]any{"id": "native-surface", "project_id": "project", "name": "Chat", "description": nil, "target_type": "agent", "target_id": "native-agent", "updated_at": revision, "allowed_origins": []any{}, "appearance_config": map[string]any{}, "requests_per_minute": 60, "max_concurrent_runs": 2, "session_token_ttl_seconds": 300}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				switch r.Method {
				case "POST":
					creates++
					if scenario == "rejected" && creates == 1 {
						w.WriteHeader(422)
						_ = json.NewEncoder(w).Encode(map[string]any{"success": false})
						return
					}
					if scenario == "unknown" {
						w.WriteHeader(503)
						_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "temporary"})
						return
					}
				case "PATCH":
					patches++
					if r.Header.Get("If-Match") != "\""+revision+"\"" {
						t.Error("missing CAS", r.Header)
					}
					var body map[string]any
					_ = json.NewDecoder(r.Body).Decode(&body)
					remote["description"] = body["description"]
					remote["updated_at"] = "2026-10-07T00:01:00Z"
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": remote})
			}))
			defer server.Close()
			c, err := devworkspace.Create(".", ".woobe", "")
			if err != nil {
				t.Fatal(err)
			}
			agent, err := c.Add("Agent", "support", "", map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "Agent", "metadata": map[string]any{"key": "support", "name": "Support"}, "spec": map[string]any{"legacy_system_prompt": "Help"}}, nil, false)
			if err != nil {
				t.Fatal(err)
			}
			document := surfaceAuthor(remote, "chat", "support")
			surface, err := c.Add("Surface", "chat", "", document, nil, false)
			if err != nil {
				t.Fatal(err)
			}
			state, _ := c.ReadState(server.URL, "workspace", "project")
			state.Bindings[agent.UID] = devworkspace.Binding{ResourceID: "native-agent"}
			if err = c.WriteState(state); err != nil {
				t.Fatal(err)
			}
			invokeAction := func(action string) (int, map[string]any) {
				return invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json", "surface", "@chat", action, "--yes"}, "")
			}
			code, result := invokeAction("create")
			if scenario == "unknown" {
				if code == 0 {
					t.Fatal(result)
				}
				code, _ = invokeAction("create")
				if code != 10 || creates != 1 {
					t.Fatal("replayed uncertain create", code, creates)
				}
				return
			}
			if scenario == "rejected" {
				if code != 2 {
					t.Fatal(code, result)
				}
				code, result = invokeAction("create")
			}
			if code != 0 {
				t.Fatal(code, result)
			}
			state, _ = c.ReadState(server.URL, "workspace", "project")
			if state.Bindings[surface.UID].ResourceID != "native-surface" {
				t.Fatal(state)
			}
			document["metadata"].(map[string]any)["description"] = "Edited locally"
			data, _ := devworkspace.Encode(document)
			if err = os.WriteFile(filepath.Join(c.RootPath(), surface.Path, "surface.yaml"), data, 0600); err != nil {
				t.Fatal(err)
			}
			if scenario == "stale" {
				remote["updated_at"] = "2026-10-07T00:02:00Z"
			}
			code, result = invokeAction("push")
			if scenario == "stale" {
				if code != 6 || patches != 0 {
					t.Fatal(code, result, patches)
				}
				return
			}
			expectedCreates := 1
			if scenario == "rejected" {
				expectedCreates = 2
			}
			if code != 0 || creates != expectedCreates || patches != 1 || remote["description"] != "Edited locally" {
				t.Fatal(code, result, creates, patches, remote)
			}
			state, _ = c.ReadState(server.URL, "workspace", "project")
			if state.Bindings[surface.UID].Revision != "2026-10-07T00:01:00Z" {
				t.Fatal(state)
			}
			code, result = invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json", "resources", "push", "--kind", "surface", "--dry-run"}, "")
			if code != 0 {
				t.Fatal("bulk Surface failed", code, result)
			}

		})
	}
}
