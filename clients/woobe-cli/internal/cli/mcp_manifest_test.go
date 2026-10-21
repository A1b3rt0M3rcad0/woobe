package cli

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestInvalidMCPManifestStoppedBeforeWrite(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++ }))
	defer server.Close()
	plan := `{"schema_version":"1","project_id":"p","steps":[{"id":"mcp","command":"project tool mcp bulk","body":{"tool_id":"11111111-1111-4111-8111-111111111111","mode":"all"}}]}`
	code, v := invoke(t, []string{"manifest", "apply", "--project", "p", "--api-url", server.URL, "--file", "-", "--yes", "--checkpoint", filepath.Join(t.TempDir(), "cp")}, plan)
	if code != 10 || calls != 0 {
		t.Fatal(code, v, calls)
	}
	cp := v["data"].(map[string]any)["checkpoint"].(map[string]any)
	if cp["steps"].(map[string]any)["mcp"] != "not_attempted" {
		t.Fatal(v)
	}
}
