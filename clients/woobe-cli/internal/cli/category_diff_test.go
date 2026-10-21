package cli

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCategoryRevisionDiffIsReadOnlyAndExplicit(t *testing.T) {
	reads := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Fatal(r.Method)
		}
		if r.URL.Path == "/openapi.json" {
			w.Write([]byte(`{"paths":{"/identity/workspaces/{workspace_id}/authority-categories/{category_id}":{"get":{"operationId":"get"}}}}`))
			return
		}
		reads++
		rev := r.URL.Query().Get("revision")
		fmt.Fprintf(w, `{"data":{"id":"c","workspace_id":"w","revision":%s,"name":"reader","description":null,"scope":"project","permissions":["agent:read"],"conditions":{},"catalog_revision":"catalog"}}`, rev)
	}))
	defer s.Close()
	code, v := invoke(t, []string{"workspace", "authority", "category", "diff", "c", "--from-revision", "1", "--to-revision", "2", "--workspace", "w", "--api-url", s.URL}, "")
	if code != 0 || reads != 2 {
		t.Fatal(code, v, reads)
	}
	d := v["data"].(map[string]any)
	if d["grants_changed"] != false || len(d["changes"].([]any)) != 0 {
		t.Fatal(d)
	}
}

func TestCategoryRevisionDiffDryRunDoesNotDiscoverOrRead(t *testing.T) {
	requests := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++; w.WriteHeader(500) }))
	defer s.Close()
	code, v := invoke(t, []string{"workspace", "authority", "category", "diff", "c", "--from-revision", "1", "--to-revision", "2", "--workspace", "w", "--api-url", s.URL, "--dry-run"}, "")
	if code != 0 || requests != 0 || v["data"].(map[string]any)["comparison"] != "not_evaluated_dry_run" {
		t.Fatal(code, v, requests)
	}
}
