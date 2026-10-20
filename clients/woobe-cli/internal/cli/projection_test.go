package cli

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestResourceProjectionKeepsPartialState(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" || r.URL.Path != "/network/projects/p/networks/n" {
			t.Error(r.Method, r.URL.Path)
		}
		w.Header().Set("ETag", "rev")
		_, _ = w.Write([]byte(`{"data":{"id":"n","name":"N","api_key":"private"}}`))
	}))
	defer s.Close()
	p := filepath.Join(t.TempDir(), "projection.json")
	code, v := invoke(t, []string{"export", "n", "--command", "project network get", "--project", "p", "--api-url", s.URL, "--destination", p}, "")
	b, _ := os.ReadFile(p)
	if code != 0 || strings.Contains(string(b), "private") || v["data"].(map[string]any)["apply_ready"] != false {
		t.Fatal(v, string(b))
	}
}
