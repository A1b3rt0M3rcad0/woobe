package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
)

func authoritySchema(w http.ResponseWriter) {
	_, _ = w.Write([]byte(`{"paths":{"/identity/workspaces/{workspace_id}/authority-categories":{"get":{"operationId":"list"}},"/identity/workspaces/{workspace_id}/authority-categories/{category_id}/versions":{"get":{"operationId":"history"}},"/identity/workspaces/{workspace_id}/authority-audit":{"get":{"operationId":"audit"}}}}`))
}

func TestCategoryHistoryAllUsesReviewedRevisionProtocol(t *testing.T) {
	requests := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			authoritySchema(w)
			return
		}
		requests++
		if r.Method != "GET" || r.URL.Path != "/identity/workspaces/w/authority-categories/c/versions" || r.URL.Query().Get("limit") != "1" {
			t.Error(r.URL)
		}
		if requests == 1 {
			_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"revision":2}],"complete":false,"next_revision":2}}`))
		} else {
			if r.URL.Query().Get("before_revision") != "2" {
				t.Error(r.URL)
			}
			_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"revision":1,"number":9007199254740993}],"complete":true,"next_revision":null}}`))
		}
	}))
	defer s.Close()
	code, v := invoke(t, []string{"workspace", "authority", "category", "history", "c", "--workspace", "w", "--api-url", s.URL, "--limit", "1", "--all"}, "")
	if code != 0 || requests != 2 || v["meta"].(map[string]any)["complete"] != true {
		t.Fatal(code, v, requests)
	}
	data := v["data"].(map[string]any)
	if data["page_count"] != float64(2) || data["collection_complete"] != "verified" || data["protocol"] != "revision-complete" {
		t.Fatal(v)
	}
}

func TestSinglePageReportsPartialCollectionWithoutChangingServerShape(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			authoritySchema(w)
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"id":"a"}],"system_categories":[{"id":"builtin"}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"workspace", "authority", "category", "list", "--workspace", "w", "--api-url", s.URL, "--limit", "1"}, "")
	meta := v["meta"].(map[string]any)
	if code != 0 || v["success"] != true || meta["complete"] != false || meta["collection_complete"] != "partial" || meta["traversal_complete"] != false {
		t.Fatal(v)
	}
	if v["data"].(map[string]any)["data"].(map[string]any)["system_categories"] == nil {
		t.Fatal("server projection lost", v)
	}
	next := meta["next_query"].(map[string]any)
	if next["cursor"].([]any)[0] != "a" || next["limit"].([]any)[0] != "1" {
		t.Fatal(meta)
	}
}

func TestRuntimeSessionsPaginationPreservesScopeAndEnvironment(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.URL.Path != "/runtime/agents/a/sessions" || r.URL.Query().Get("project_id") != "p" || r.URL.Query().Get("environment") != "production" {
			t.Error(r.URL)
		}
		if n == 1 {
			_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"id":"s1"}],"has_next":true,"next_cursor":"s1"}}`))
		} else {
			if r.URL.Query().Get("cursor") != "s1" {
				t.Error(r.URL)
			}
			_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"id":"s2"}],"has_next":false,"next_cursor":null}}`))
		}
	}))
	defer s.Close()
	code, v := invoke(t, []string{"runtime", "agent", "sessions", "a", "--project", "p", "--api-url", s.URL, "--query", "environment=production", "--all", "--limit", "1"}, "")
	if code != 0 || n != 2 || v["meta"].(map[string]any)["complete"] != true {
		t.Fatal(v)
	}
}

func TestRequestPagesAutoContractAndPartialCause(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if n == 2 {
			w.Header().Set("X-Request-ID", "denied-page")
			w.WriteHeader(403)
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"token":"hide-me"}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"request-pages", "/identity/workspaces/w/authority-audit", "--api-url", s.URL}, "")
	if code != 10 || n != 2 || v["meta"].(map[string]any)["complete"] != false || v["error"].(map[string]any)["request_id"] != "denied-page" || v["error"].(map[string]any)["http_status"] != float64(403) {
		t.Fatal(v)
	}
	page := v["data"].(map[string]any)["pages"].([]any)[0].(map[string]any)
	if page["data"].(map[string]any)["items"].([]any)[0].(map[string]any)["token"] != "[REDACTED]" {
		t.Fatal("partial secret leaked")
	}
}

func TestPageLimitProvidesExplicitContinuationAndFromMarkerScope(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("cursor") == "a" {
			_, _ = w.Write([]byte(`{"success":true,"data":{"items":[],"complete":true,"next_cursor":null}}`))
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	base := []string{"request-pages", "/items", "--pagination", "cursor-complete", "--api-url", s.URL}
	code, v := invoke(t, append(append([]string{}, base...), "--max-pages", "1"), "")
	if code != 10 || v["data"].(map[string]any)["next_query"].(map[string]any)["cursor"].([]any)[0] != "a" {
		t.Fatal(v)
	}
	code, v = invoke(t, append(append([]string{}, base...), "--query", "cursor=a"), "")
	if code != 0 || v["success"] != true || v["meta"].(map[string]any)["complete"] != false || v["meta"].(map[string]any)["collection_complete"] != "remaining" {
		t.Fatal(v)
	}
}

func TestUnknownLinkRouteCannotCertifyBodyCollection(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"request-pages", "/unknown", "--api-url", s.URL}, "")
	if code != 0 || v["meta"].(map[string]any)["complete"] != false || v["data"].(map[string]any)["collection_complete"] != "not_verified" {
		t.Fatal(v)
	}
}

func TestPaginationInputFailuresHaveZeroNetworkEffects(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { n++; authoritySchema(w) }))
	defer s.Close()
	base := []string{"workspace", "authority", "category", "history", "c", "--workspace", "w", "--api-url", s.URL}
	for _, flags := range [][]string{{"--limit", "0"}, {"--limit", "201"}, {"--max-pages", "0", "--all"}, {"--max-pages", "1"}, {"--before-revision", "bad"}, {"--before-revision", ""}, {"--limit", "2", "--query", "limit=1"}, {"--query", "limit=1", "--query", "limit=1"}, {"--query", "before_revision=0"}, {"--file", "-"}} {
		code, v := invoke(t, append(append([]string{}, base...), flags...), `{}`)
		if code != 2 {
			t.Fatal(flags, v)
		}
	}
	if n != 0 {
		t.Fatal("input validation accessed network", n)
	}
}

func TestPaginationDiscoveryAndDryRun(t *testing.T) {
	code, v := invoke(t, []string{"help", "workspace", "authority", "category", "history"}, "")
	if code != 0 || v["data"].(map[string]any)["pagination"] != "revision-complete" {
		t.Fatal(v)
	}
	flags := map[string]bool{}
	for _, flag := range v["data"].(map[string]any)["flags"].([]any) {
		flags[flag.(map[string]any)["name"].(string)] = true
	}
	if !flags["all"] || !flags["limit"] || !flags["before-revision"] || !flags["max-pages"] {
		t.Fatal(flags)
	}
	code, v = invoke(t, []string{"runtime", "agent", "sessions", "a", "--project", "p", "--limit", "2", "--all", "--dry-run"}, "")
	if code != 0 || v["data"].(map[string]any)["executed"] != false || v["data"].(map[string]any)["query"].(map[string]any)["project_id"].([]any)[0] != "p" {
		t.Fatal(v)
	}
	if paginationForPath("/identity/workspaces/w/authority-categories/c") != "" || paginationForPath("/runtime/agents/a/sessions/extra") != "" || paginationForPath("/runtime/agents//sessions") != "" {
		t.Fatal("contract route mismatch")
	}
}

func TestPagedTableRetainsMetadataAndPartialResults(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{"id":"received","token":"hide-me"}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	out := &bytes.Buffer{}
	a := New(&bytes.Buffer{}, out, &bytes.Buffer{})
	code := a.Execute(context.Background(), []string{"request-pages", "/items", "--pagination", "cursor-complete", "--api-url", s.URL, "--max-pages", "1", "--output", "table", "--config", filepath.Join(t.TempDir(), "config.json")})
	if code != 10 || !strings.Contains(out.String(), "received") || !strings.Contains(out.String(), "collection_complete") || strings.Contains(out.String(), "hide-me") {
		t.Fatal(out.String())
	}
}

func TestPageMetadataRedactsSensitiveQueryParameters(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"request-pages", "/items", "--pagination", "cursor-complete", "--api-url", s.URL, "--max-pages", "1", "--query", "token=query-secret"}, "")
	if code != 10 {
		t.Fatal(v)
	}
	encoded, _ := json.Marshal(v)
	if strings.Contains(string(encoded), "query-secret") {
		t.Fatal("metadata secret leaked")
	}
	if v["data"].(map[string]any)["protocol"] != string(controlplane.CursorComplete) {
		t.Fatal(v)
	}
}
