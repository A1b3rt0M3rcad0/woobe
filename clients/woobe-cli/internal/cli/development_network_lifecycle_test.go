package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestNetworkLifecycleCarriesPreviewRevisionAndOnlyApprovedActions(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	for _, action := range []string{"stage", "publish"} {
		t.Run(action, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				var body map[string]any
				_ = json.NewDecoder(r.Body).Decode(&body)
				environment := "staging"
				if action == "publish" {
					environment = "production"
				}
				if body["environment"] != environment || body["project_id"] != "project" {
					t.Error(body)
				}
				if strings.HasSuffix(r.URL.Path, "/preview") {
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"ready": true, "network_revision": 7, "network_version_id": "staging-id", "actions": []any{map[string]any{"id": "content-bound-action"}}}})
				} else {
					if action == "stage" && body["expected_revision"] != float64(7) {
						t.Error(body)
					}
					if action == "publish" && body["expected_network_version_id"] != "staging-id" {
						t.Error(body)
					}
					approvals, ok := body["approved_action_ids"].([]any)
					if !ok || len(approvals) != 1 || approvals[0] != "content-bound-action" {
						t.Error(body)
					}
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"id": "network-version"}})
				}
			}))
			defer server.Close()
			code, reply := invoke(t, []string{"--api-url", server.URL, "--project", "project", "network", "native-network", action, "--yes", "--output", "json"}, "")
			if code != 0 || requests != 2 {
				t.Fatal(code, reply, requests)
			}
		})
	}
}

func TestAgentDeleteRetainsHistoryThroughGuardedNativeArchive(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method == "GET" {
			_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"revision": 12}})
			return
		}
		if r.Method != "DELETE" || r.Header.Get("If-Match") != "\"12\"" {
			t.Error(r.Method, r.Header.Get("If-Match"))
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"status": "archived"}})
	}))
	defer server.Close()
	code, reply := invoke(t, []string{"--api-url", server.URL, "--project", "project", "agent", "native-agent", "delete", "--yes", "--output", "json"}, "")
	if code != 0 || requests != 2 {
		t.Fatal(code, reply, requests)
	}
}
