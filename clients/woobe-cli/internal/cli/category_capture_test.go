package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCategoryCapturePreservesWorkspaceAndETag(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" || r.URL.Path != "/identity/workspaces/w/authority-categories/c" {
			t.Error(r.Method, r.URL.Path)
		}
		w.Header().Set("ETag", `"category:c:2"`)
		w.Write([]byte(`{"data":{"id":"c","workspace_id":"w","name":"reader","permissions":["agent:read"]}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "capture", "--kind", "AuthorityCategory", "--id", "c", "--workspace", "w", "--field", "name", "--field", "permissions", "--api-url", s.URL}, "")
	if code != 0 {
		t.Fatal(v)
	}
	d := v["data"].(map[string]any)["document"].(map[string]any)
	if d["workspace_id"] != "w" {
		t.Fatal(d)
	}
	resources := d["resources"].([]any)
	if resources[0].(map[string]any)["if_match"] != `"category:c:2"` {
		t.Fatal(d)
	}
	code, _ = invoke(t, []string{"manifest", "capture", "--kind", "AuthorityCategory", "--id", "c", "--workspace", "w", "--field", "grants", "--api-url", s.URL}, "")
	if code != 5 && code != 2 {
		t.Fatal(code)
	}
}
