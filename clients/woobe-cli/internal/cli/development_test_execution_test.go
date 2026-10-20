package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestYAMLReleaseTestSelectsStagingAndReturnsOneTerminalEnvelope(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	for _, status := range []string{"passed", "failed"} {
		t.Run(status, func(t *testing.T) {
			requests, schemas := 0, 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if serveReleaseTestSchema(w, r) {
					schemas++
					return
				}
				requests++
				var body map[string]any
				_ = json.NewDecoder(r.Body).Decode(&body)
				var data any
				if strings.HasSuffix(r.URL.Path, "/export") {
					if body["source"] != "staging" {
						t.Error(body)
					}
					data = map[string]any{"package_schema_version": "1.0", "export_id": "export", "project_id": "project", "closure_complete": true, "artifact_digest": strings.Repeat("a", 64), "transport_digest": strings.Repeat("b", 64), "size_bytes": 10, "inventory": []any{map[string]any{"path": "agent.yaml"}}, "knowledge": "binding", "expires_at": time.Now().Add(time.Hour).UTC().Format(time.RFC3339), "source": map[string]any{"snapshot_id": "selected-staging"}}
				} else {
					if r.Method != "POST" || r.URL.Path != "/ai/agents/native-agent/release-tests/run" || body["message"] != "Hello" || body["release_id"] != "selected-staging" || body["environment"] != "staging" {
						t.Error(r.URL.Path, body)
					}
					data = map[string]any{"id": "native-test", "status": status, "actual_output": map[string]any{"answer": "Actual"}, "latency_ms": 10}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, reply := invoke(t, []string{"--api-url", server.URL, "--project", "project", "agent", "native-agent", "test", "--file", "-", "--yes", "--output", "json"}, "message: Hello\nexpected_output:\n  answer: Actual\n")
			want := 0
			if status == "failed" {
				want = 6
			}
			if code != want || requests != 2 || schemas != 1 || reply["data"].(map[string]any)["status"] != status {
				t.Fatal(code, reply, requests)
			}
		})
	}
}
