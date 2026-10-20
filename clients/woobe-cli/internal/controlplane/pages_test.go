package controlplane

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"
)

func TestAdvertisedPagesStayScoped(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.URL.Query().Get("project_id") != "p" {
			t.Error("scope lost")
		}
		if n == 1 {
			w.Header().Set("Link", `<?project_id=p&page=2>; rel="next"`)
		}
		_, _ = w.Write([]byte(`{"data":[{"id":"a"}]}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	p, e := c.RequestPages(context.Background(), "/items", url.Values{"project_id": {"p"}}, 5)
	if e != nil || p.Count != 2 || !p.TraversalComplete || p.CollectionComplete != "not_verified" {
		t.Fatal(p, e)
	}
}
func TestPaginationRejectsForeignRouteScopeAndLoops(t *testing.T) {
	for _, next := range []string{`<https://foreign.invalid/items>; rel="next"`, `</different>; rel="next"`, `<?project_id=other>; rel="next"`, `<?project_id=p>; rel="next"`} {
		n := 0
		s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			n++
			w.Header().Set("Link", next)
			_, _ = w.Write([]byte(`[]`))
		}))
		c, _ := New(s.URL, "", time.Second)
		p, e := c.RequestPages(context.Background(), "/items", url.Values{"project_id": {"p"}}, 3)
		s.Close()
		if e == nil || n != 1 || p.TraversalComplete {
			t.Fatal(next, n, e)
		}
	}
}
func TestPageLimitPreservesReceivedPages(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Link", `<?page=2>; rel="next"`)
		_, _ = w.Write([]byte(`[]`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	p, e := c.RequestPages(context.Background(), "/items", nil, 1)
	if e == nil || p.Count != 1 || p.TraversalComplete {
		t.Fatal(p, e)
	}
}
