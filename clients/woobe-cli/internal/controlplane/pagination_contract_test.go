package controlplane

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func pageValue(t *testing.T, raw string) any {
	t.Helper()
	var v any
	decoder := json.NewDecoder(strings.NewReader(raw))
	decoder.UseNumber()
	if e := decoder.Decode(&v); e != nil {
		t.Fatal(e)
	}
	return v
}

func TestReviewedBodyPaginationTraversesAllProtocols(t *testing.T) {
	for _, contract := range []PaginationContract{CursorComplete, CursorHasNext, RevisionComplete} {
		t.Run(string(contract), func(t *testing.T) {
			var queries []url.Values
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != "GET" {
					t.Error("pagination wrote")
				}
				q := r.URL.Query()
				queries = append(queries, q)
				if q.Get("project_id") != "p" || q.Get("environment") != "staging" || q.Get("limit") != "1" || len(q["tag"]) != 2 {
					t.Error("filter changed", q)
				}
				data := map[string]any{"items": []any{map[string]any{"id": "9007199254740993"}}}
				terminal := len(queries) == 3
				field := "next_cursor"
				if contract == RevisionComplete {
					field = "next_revision"
				}
				data[field] = nil
				if !terminal {
					if contract == RevisionComplete {
						data[field] = 4 - len(queries)
					} else {
						data[field] = "opaque-" + strings.Repeat("x", len(queries))
					}
				}
				if contract == CursorHasNext {
					data["has_next"] = !terminal
				} else {
					data["complete"] = terminal
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer s.Close()
			client, _ := New(s.URL, "", time.Second)
			q := url.Values{"project_id": {"p"}, "environment": {"staging"}, "limit": {"1"}, "tag": {"a", "b"}}
			pages, e := client.RequestPagesWithContract(context.Background(), "/items", q, 3, contract)
			if e != nil || pages.Count != 3 || !pages.TraversalComplete || pages.CollectionComplete != "verified" || pages.StartedFromMarker || pages.NextQuery != nil {
				t.Fatal(pages, e)
			}
			if q.Get(contract.Marker()) != "" {
				t.Fatal("caller query mutated")
			}
		})
	}
}

func TestPaginationStartedAtCursorDoesNotClaimWholeCollection(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[],"next_cursor":null,"complete":true}}`))
	}))
	defer s.Close()
	client, _ := New(s.URL, "", time.Second)
	pages, e := client.RequestPagesWithContract(context.Background(), "/items", url.Values{"cursor": {"after"}}, 2, CursorComplete)
	if e != nil || !pages.TraversalComplete || pages.CollectionComplete != "remaining" || !pages.StartedFromMarker || pages.Metadata()["complete"] != false {
		t.Fatal(pages, e)
	}
}

func TestBodyPaginationRejectsAmbiguousAndInconsistentPages(t *testing.T) {
	cases := []struct {
		contract PaginationContract
		raw      string
		query    url.Values
	}{
		{CursorComplete, `{"success":true,"data":{"items":[],"complete":true}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":[],"complete":true,"next_cursor":"unexpected"}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":[],"complete":false,"next_cursor":"x"}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":null}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":" "}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":[{}],"complete":"true","next_cursor":null}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":{},"complete":true,"next_cursor":null}}`, nil},
		{CursorComplete, `{"data":{"items":[],"complete":true,"next_cursor":null}}`, nil},
		{CursorComplete, `[]`, nil},
		{CursorComplete, `{"success":true,"data":[]}`, nil},
		{CursorHasNext, `{"success":true,"data":{"items":[{}],"has_next":true,"next_cursor":123}}`, nil},
		{CursorComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":"x"}}`, url.Values{"cursor": {"x"}}},
		{RevisionComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_revision":"2"}}`, nil},
		{RevisionComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_revision":2.0}}`, nil},
		{RevisionComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_revision":0}}`, nil},
		{RevisionComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_revision":9223372036854775808}}`, nil},
		{RevisionComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_revision":3}}`, url.Values{"before_revision": {"3"}}},
		{RevisionComplete, `{"success":true,"data":{"items":[{}],"complete":false,"next_revision":4}}`, url.Values{"before_revision": {"3"}}},
	}
	for _, c := range cases {
		state, e := InspectPage(pageValue(t, c.raw), c.query, c.contract)
		if e == nil || state.TraversalComplete || state.CollectionComplete == "verified" {
			t.Fatal(c.raw, state, e)
		}
	}
}

func TestBodyPaginationLimitCycleAndHTTPFailureKeepPartialEvidence(t *testing.T) {
	for _, scenario := range []string{"limit", "cycle", "http"} {
		t.Run(scenario, func(t *testing.T) {
			n := 0
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				n++
				if scenario == "http" && n == 2 {
					w.Header().Set("X-Request-ID", "failed-page")
					w.WriteHeader(403)
					return
				}
				next := "a"
				if n == 2 {
					next = "b"
				}
				_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":"` + next + `"}}`))
			}))
			defer s.Close()
			client, _ := New(s.URL, "", time.Second)
			max := 4
			if scenario == "limit" {
				max = 1
			}
			pages, e := client.RequestPagesWithContract(context.Background(), "/items", nil, max, CursorComplete)
			if e == nil || pages.Count < 1 || pages.TraversalComplete || pages.CollectionComplete != "partial" {
				t.Fatal(pages, e)
			}
			if scenario == "limit" && (n != 1 || pages.NextQuery.Get("cursor") != "a") {
				t.Fatal(pages)
			}
			if scenario == "cycle" && n != 3 {
				t.Fatal("cycle followed", n)
			}
			if scenario == "http" && (pages.Count != 1 || output.Normalize(e).RequestID != "failed-page") {
				t.Fatal(pages, e)
			}
		})
	}
}

func TestPaginationDeadlineBoundsWholeTraversal(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("cursor") == "a" {
			<-r.Context().Done()
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"data":{"items":[{}],"complete":false,"next_cursor":"a"}}`))
	}))
	defer s.Close()
	client, _ := New(s.URL, "", 100*time.Millisecond)
	pages, e := client.RequestPagesWithContract(context.Background(), "/items", nil, 10, CursorComplete)
	if output.Normalize(e).Code != 8 || pages.Count != 1 || pages.TraversalComplete {
		t.Fatal(pages, e)
	}
}

func TestPaginationInvalidQueriesNeverReachServer(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { n++ }))
	defer s.Close()
	client, _ := New(s.URL, "", time.Second)
	for _, q := range []url.Values{{"cursor": {"a", "b"}}, {"cursor": {""}}, {"limit": {"0"}}, {"limit": {"201"}}, {"limit": {"1", "1"}}, {"cursor": {strings.Repeat("x", 8193)}}} {
		if _, e := client.RequestPagesWithContract(context.Background(), "/items", q, 2, CursorComplete); e == nil {
			t.Fatal(q)
		}
	}
	if n != 0 {
		t.Fatal("invalid query sent")
	}
}

func TestLinkPaginationPreservesAllFilters(t *testing.T) {
	for _, next := range []string{`<?project_id=p&page=2>; rel="next"`, `<?project_id=p&environment=production&page=2>; rel="next"`, `<?project_id=p&environment=staging&limit=2&page=2>; rel="next"`, `<?project_id=p&environment=staging&limit=1&user_id=other&page=2>; rel="next"`, `<?project_id=p&environment=staging&limit=1&bad=%XX&page=2>; rel="next"`} {
		n := 0
		s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			n++
			w.Header().Set("Link", next)
			_, _ = w.Write([]byte(`[]`))
		}))
		client, _ := New(s.URL, "", time.Second)
		pages, e := client.RequestPages(context.Background(), "/items", url.Values{"project_id": {"p"}, "environment": {"staging"}, "limit": {"1"}}, 2)
		s.Close()
		if e == nil || n != 1 || pages.TraversalComplete {
			t.Fatal(next, pages, e)
		}
	}
}
