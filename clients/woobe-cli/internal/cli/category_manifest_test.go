package cli

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestCategoryManifestOfflineCompilationAndScope(t *testing.T) {
	code, v := invoke(t, []string{"manifest", "compile", "--file", "-"}, `{"schema_version":"2","workspace_id":"w","resources":[{"key":"reader","kind":"AuthorityCategory","action":"create","spec":{"name":"reader","permissions":["agent:read"]}}]}`)
	if code != 0 || v["data"].(map[string]any)["executed"] != false {
		t.Fatal(code, v)
	}
	for _, command := range []string{"workspace authority category clone", "workspace authority category archive"} {
		code, _ := invoke(t, []string{"manifest", "validate", "--file", "-"}, `{"schema_version":"1","workspace_id":"w","steps":[{"id":"c","command":"`+command+`","args":["c"],"body":{}}]}`)
		if code != 9 {
			t.Fatal(command, code)
		}
	}
	code, _ = invoke(t, []string{"manifest", "validate", "--file", "-"}, `{"schema_version":"1","steps":[{"id":"c","command":"workspace authority category create","body":{}}]}`)
	if code != 2 {
		t.Fatal(code)
	}
}

func TestStepCategoryManifestCannotBypassDefinitionBoundary(t *testing.T) {
	for _, field := range []string{"grants", "workspace_id", "category_id", "system", "status"} {
		code, _ := invoke(t, []string{"manifest", "validate", "--file", "-"}, `{"schema_version":"1","workspace_id":"w","steps":[{"id":"c","command":"workspace authority category create","body":{"`+field+`":"value"}}]}`)
		if code != 2 {
			t.Fatal(field, code)
		}
	}
}

func TestCategoryManifestApplyAndResumeNeverAssignsGrants(t *testing.T) {
	writes := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			w.Write([]byte(`{"paths":{"/identity/workspaces/{workspace_id}/authority-categories":{"post":{"operationId":"create"}}}}`))
			return
		}
		if r.Method != "POST" || r.URL.Path != "/identity/workspaces/w/authority-categories" {
			t.Error(r.Method, r.URL.Path)
			w.WriteHeader(404)
			return
		}
		writes++
		w.Write([]byte(`{"data":{"id":"c","workspace_id":"w","revision":1}}`))
	}))
	defer s.Close()
	dir := t.TempDir()
	args := []string{"manifest", "apply", "--workspace", "w", "--api-url", s.URL, "--file", "-", "--checkpoint", filepath.Join(dir, "checkpoint"), "--config", filepath.Join(dir, "config"), "--yes"}
	body := `{"schema_version":"2","workspace_id":"w","resources":[{"key":"c","kind":"AuthorityCategory","action":"create","spec":{"name":"reader","permissions":["agent:read"]}}]}`
	for i := 0; i < 2; i++ {
		code, v := invoke(t, args, body)
		if code != 0 {
			t.Fatal(code, v)
		}
	}
	if writes != 1 {
		t.Fatal("create repeated", writes)
	}
}

func TestCategoryManifestAbsentAdvertisementRefusesWrite(t *testing.T) {
	writes := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
		}
		w.Write([]byte(`{"paths":{}}`))
	}))
	defer s.Close()
	dir := t.TempDir()
	code, v := invoke(t, []string{"manifest", "apply", "--workspace", "w", "--api-url", s.URL, "--file", "-", "--checkpoint", filepath.Join(dir, "checkpoint"), "--config", filepath.Join(dir, "config"), "--yes"}, `{"schema_version":"2","workspace_id":"w","resources":[{"key":"c","kind":"AuthorityCategory","action":"create","spec":{"name":"reader","permissions":[]}}]}`)
	if code != 10 || writes != 0 {
		t.Fatal(code, writes, v)
	}
	data := v["data"].(map[string]any)
	if data["cause"].(map[string]any)["exit_code"] != float64(9) || data["checkpoint"].(map[string]any)["steps"].(map[string]any)["c"] != "not_attempted" {
		t.Fatal(data)
	}
}
