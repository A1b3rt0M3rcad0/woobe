package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestResourceApplyResolvesIDsAndSkipsUnchangedUpdates(t *testing.T) {
	creates, reads, patches := 0, 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method + " " + r.URL.Path {
		case "POST /ai/agents":
			creates++
			_, _ = w.Write([]byte(`{"data":{"id":"a","name":"A"}}`))
		case "POST /ai/agents/a/prompts":
			creates++
			_, _ = w.Write([]byte(`{"data":{"id":"prompt"}}`))
		case "GET /network/projects/p/networks/n":
			reads++
			w.Header().Set("ETag", "rev")
			_, _ = w.Write([]byte(`{"data":{"id":"n","description":null,"untouched":"keep"}}`))
		case "PATCH /network/projects/p/networks/n":
			patches++
		default:
			t.Error(r.Method, r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	defer s.Close()
	dir := t.TempDir()
	cp := filepath.Join(dir, "cp")
	body := `{"schema_version":"2","project_id":"p","resources":[{"key":"a","kind":"Agent","action":"create","spec":{"name":"A"}},{"key":"prompt","kind":"AgentPrompt","action":"create","parents":{"agent":"${resources.a.id}"},"depends_on":["a"],"spec":{"content":"Teach"}},{"key":"n","kind":"Network","action":"update","resource_id":"n","spec":{"description":null},"if_match":"rev"}]}`
	args := []string{"manifest", "apply", "--file", "-", "--api-url", s.URL, "--project", "p", "--config", filepath.Join(dir, "config"), "--checkpoint", cp, "--yes", "--skip-unchanged"}
	for i := 0; i < 2; i++ {
		out := &bytes.Buffer{}
		a := New(bytes.NewBufferString(body), out, &bytes.Buffer{})
		if code := a.Execute(context.Background(), args); code != 0 {
			t.Fatal(code, out.String())
		}
	}
	if creates != 2 || reads != 1 || patches != 0 {
		t.Fatal(creates, reads, patches)
	}
	b, _ := os.ReadFile(cp)
	var c checkpoint
	_ = json.Unmarshal(b, &c)
	if c.Steps["n"] != "unchanged" {
		t.Fatal(c)
	}
}
func TestResourceDiffReadsExplicitIdentity(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.Method != "GET" || r.URL.Path != "/ai/agents/a" {
			t.Error(r.Method, r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"data":{"id":"a","name":"old","description":"keep"}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "diff", "--file", "-", "--project", "p", "--api-url", s.URL}, `{"schema_version":"2","project_id":"p","resources":[{"key":"a","kind":"Agent","action":"update","resource_id":"a","spec":{"name":"new"}}]}`)
	if code != 0 || n != 1 {
		t.Fatal(v, n)
	}
}
