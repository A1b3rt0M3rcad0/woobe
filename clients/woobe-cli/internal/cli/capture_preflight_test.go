package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCaptureInvalidSelectionDoesNotRead(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { n++; w.WriteHeader(500) }))
	defer s.Close()
	for _, fields := range [][]string{{"--field", "token"}, {"--field", "name", "--field", "name"}} {
		args := append([]string{"manifest", "capture", "--kind", "Agent", "--id", "a", "--project", "p", "--api-url", s.URL}, fields...)
		code, _ := invoke(t, args, "")
		if code != 2 || n != 0 {
			t.Fatal(code, n)
		}
	}
}
