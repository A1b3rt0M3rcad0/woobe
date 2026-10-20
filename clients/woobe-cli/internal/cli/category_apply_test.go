package cli

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestCategoryApplySkipsOnlyIdentityBoundUnchangedDefinition(t *testing.T) {
	reads, writes := 0, 0
	etag := `"category:c:2"`
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method + " " + r.URL.Path {
		case "GET /openapi.json":
			w.Write([]byte(`{"paths":{"/identity/workspaces/{workspace_id}/authority-categories/{category_id}":{"patch":{"operationId":"update"}}}}`))
		case "GET /identity/workspaces/w/authority-categories/c":
			reads++
			w.Header().Set("ETag", etag)
			w.Write([]byte(`{"data":{"id":"c","workspace_id":"w","revision":2,"permissions":["agent:read","agent:write"],"conditions":{"interfaces":["http","stream"]}}}`))
		case "PATCH /identity/workspaces/w/authority-categories/c":
			writes++
			w.Write([]byte(`{"data":{"id":"c"}}`))
		default:
			t.Error(r.Method, r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	defer s.Close()
	body := `{"schema_version":"2","workspace_id":"w","resources":[{"key":"c","kind":"AuthorityCategory","action":"update","resource_id":"c","if_match":"\"category:c:2\"","spec":{"permissions":["agent:write","agent:read"],"conditions":{"interfaces":["stream","http"]}}}]}`
	run := func() (int, map[string]any) {
		dir := t.TempDir()
		return invoke(t, []string{"manifest", "apply", "--workspace", "w", "--api-url", s.URL, "--file", "-", "--skip-unchanged", "--checkpoint", filepath.Join(dir, "cp"), "--config", filepath.Join(dir, "config"), "--yes"}, body)
	}
	code, v := run()
	if code != 0 || writes != 0 || reads != 1 {
		t.Fatal(code, v, reads, writes)
	}
	etag = `"category:c:3"`
	code, v = run()
	if code != 10 || writes != 0 {
		t.Fatal(code, v, writes)
	}
	if v["data"].(map[string]any)["checkpoint"].(map[string]any)["steps"].(map[string]any)["c"] != "not_attempted" {
		t.Fatal(v)
	}
}
