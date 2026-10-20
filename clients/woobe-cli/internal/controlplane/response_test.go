package controlplane

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestMalformedSuccessfulWriteIsUncertain(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Request-ID", "id")
		_, _ = w.Write([]byte(`not json`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	_, _, e := c.Request(context.Background(), "POST", "/x", nil, []byte(`{}`))
	v := output.Normalize(e)
	if v.Outcome != "unknown" || v.RequestID != "id" {
		t.Fatal(v)
	}
}
