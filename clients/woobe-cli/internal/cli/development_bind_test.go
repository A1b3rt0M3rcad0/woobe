package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestProviderBindingVerifiesDestinationWithoutCopyingSecrets(t *testing.T) {
	for _, scenario := range []string{"valid", "foreign", "inactive", "mismatch", "missing"} {
		t.Run(scenario, func(t *testing.T) {
			t.Chdir(t.TempDir())
			t.Setenv("WOOBE_CONTROL_KEY", "test")
			c, err := devworkspace.Create(".", ".woobe", "")
			if err != nil {
				t.Fatal(err)
			}
			resource, err := c.Add("Provider", "openai", "", map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "Provider", "metadata": map[string]any{"key": "openai", "name": "OpenAI"}, "spec": map[string]any{"provider": "openai"}}, nil, false)
			if err != nil {
				t.Fatal(err)
			}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != "GET" || r.URL.Path != "/ai/credentials" || r.URL.Query().Get("project_id") != "project" {
					t.Error(r.Method, r.URL)
				}
				entry := map[string]any{"id": "native-credential", "project_id": "project", "provider": "openai", "status": "active"}
				switch scenario {
				case "foreign":
					entry["project_id"] = "foreign"
				case "inactive":
					entry["status"] = "revoked"
				case "mismatch":
					entry["provider"] = "anthropic"
				case "missing":
					entry["id"] = "other"
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": []any{entry}})
			}))
			defer server.Close()
			args := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json", "resources", "bind", "provider", "@openai", "native-credential"}
			code, result := invoke(t, args, "")
			if scenario == "valid" && code != 0 {
				t.Fatal(code, result)
			}
			if scenario != "valid" && code != 6 {
				t.Fatal(code, result)
			}
			state, err := c.ReadState(server.URL, "workspace", "project")
			if err != nil {
				t.Fatal(err)
			}
			if scenario == "valid" && state.Bindings[resource.UID].ResourceID != "native-credential" {
				t.Fatal("binding cannot be reused by pull", state)
			}
			if scenario == "valid" && state.Credentials[resource.Key] != "native-credential" {
				t.Fatal(state)
			}
			if scenario != "valid" && len(state.Credentials) != 0 {
				t.Fatal("failed check persisted identity")
			}
			// Idempotent same identity; different destination remains unbound.
			if scenario == "valid" {
				code, result = invoke(t, args, "")
				if code != 0 {
					t.Fatal(code, result)
				}
				foreign, _ := c.ReadState(server.URL, "workspace", "another")
				if len(foreign.Credentials) != 0 {
					t.Fatal("binding escaped project scope")
				}
			}
		})
	}
}
