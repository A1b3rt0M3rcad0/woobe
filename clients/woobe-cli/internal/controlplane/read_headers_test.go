package controlplane

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestReadOmitsMutationHeaders(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("If-Match") != "" || r.Header.Get("Idempotency-Key") != "" {
			t.Error("mutation headers on read")
		}
		_, _ = w.Write([]byte(`{}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	c.Headers.Set("If-Match", "rev")
	c.Headers.Set("Idempotency-Key", "key")
	_, _, e := c.Request(context.Background(), "GET", "/schema", nil, nil)
	if e != nil {
		t.Fatal(e)
	}
}
