package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestAgentLifecycleSelectsNativeSnapshotAndNeverUploadsLocalYAML(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	for _, action := range []string{"stage", "publish", "activate", "rollback"} {
		t.Run(action, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				var body map[string]any
				_ = json.NewDecoder(r.Body).Decode(&body)
				var data any
				if strings.HasSuffix(r.URL.Path, "/export") {
					env := "draft"
					if action == "publish" {
						env = "staging"
					}
					if action == "activate" || action == "rollback" {
						env = "release"
					}
					if body["source"] != env || body["knowledge"] != "binding" {
						t.Error(body)
					}
					data = map[string]any{"package_schema_version": "1.0", "export_id": "export", "project_id": "project", "closure_complete": true, "artifact_digest": strings.Repeat("a", 64), "transport_digest": strings.Repeat("b", 64), "size_bytes": 10, "inventory": []any{map[string]any{"path": "agent.yaml"}}, "knowledge": "binding", "expires_at": time.Now().Add(time.Hour).UTC().Format(time.RFC3339), "source": map[string]any{"snapshot_id": "selected-snapshot"}}
				} else {
					suffix := "promote"
					if action == "rollback" {
						suffix = "rollback"
					}
					if r.Method != "POST" || r.URL.Path != "/ai/agents/native-agent/releases/selected-snapshot/"+suffix {
						t.Error(r.Method, r.URL.Path)
					}
					if action == "stage" && (body["target_status"] != "staging" || body["copy_snapshot"] != true) {
						t.Error(body)
					}
					if action == "publish" && body["target_status"] != "released" {
						t.Error(body)
					}
					data = map[string]any{"id": "native-result"}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			args := []string{"--api-url", server.URL, "--project", "project", "agent", "native-agent", action, "--yes", "--notes", "Reviewed change", "--output", "json"}
			if action == "activate" || action == "rollback" {
				args = append(args, "--version", "1.2.0")
			}
			code, reply := invoke(t, args, "")
			if code != 0 || requests != 2 {
				t.Fatal(code, reply, requests)
			}
		})
	}
}
