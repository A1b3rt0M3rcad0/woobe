package controlplane

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHeadPreservesHeaders(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Header().Set("ETag", "rev"); w.WriteHeader(200) }))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	v, h, e := c.Request(context.Background(), "HEAD", "/x", nil, nil)
	if e != nil || v != nil || h.Get("ETag") != "rev" {
		t.Fatal(v, h, e)
	}
}
