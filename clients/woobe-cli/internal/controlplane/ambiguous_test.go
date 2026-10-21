package controlplane

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestDuplicateSuccessResponsePreservesUncertainty(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Request-ID", "req")
		w.Write([]byte(`{"data":{"id":"a","id":"b"}}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	_, _, e := c.Request(context.Background(), "POST", "/x", nil, nil)
	v := output.Normalize(e)
	if v.Code != 9 || v.Outcome != "unknown" || v.RequestID != "req" {
		t.Fatal(v)
	}
}
func TestUnsuccessfulEnvelopeKeepsRequestEvidence(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Request-ID", "req")
		w.Write([]byte(`{"success":false}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	_, _, e := c.Request(context.Background(), "PATCH", "/x", nil, nil)
	v := output.Normalize(e)
	if v.Status != 200 || v.RequestID != "req" || v.Outcome != "unknown" {
		t.Fatal(v)
	}
}
