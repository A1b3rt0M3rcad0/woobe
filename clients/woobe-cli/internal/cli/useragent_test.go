package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAdministrativeUserAgent(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.UserAgent() != "woobe-cli/"+Version {
			t.Error(r.UserAgent())
		}
		_, _ = w.Write([]byte(`{}`))
	}))
	defer s.Close()
	code, _ := invoke(t, []string{"request", "GET", "/x", "--api-url", s.URL}, "")
	if code != 0 {
		t.Fatal(code)
	}
}
