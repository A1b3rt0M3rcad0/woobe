package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestProposedDryRunDoesNotProbe(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { n++; w.WriteHeader(500) }))
	defer s.Close()
	code, _ := invoke(t, []string{"workspace", "authority", "category", "create", "--workspace", "w", "--file", "-", "--api-url", s.URL, "--dry-run"}, `{}`)
	if code != 0 || n != 0 {
		t.Fatal(code, n)
	}
}
