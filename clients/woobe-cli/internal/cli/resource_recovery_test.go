package cli

import (
	"bytes"
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestResourceCreationReconciliationResumesWithoutReplay(t *testing.T) {
	creates, prompts := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method + " " + r.URL.Path {
		case "POST /ai/agents":
			creates++
			conn, _, _ := w.(http.Hijacker).Hijack()
			_ = conn.Close()
		case "GET /ai/agents/a":
			_, _ = w.Write([]byte(`{"data":{"id":"a","project_id":"p","name":"A","temperature":1.0}}`))
		case "POST /ai/agents/a/prompts":
			prompts++
			_, _ = w.Write([]byte(`{"data":{"id":"prompt"}}`))
		default:
			t.Error(r.Method, r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	defer s.Close()
	dir := t.TempDir()
	cp := filepath.Join(dir, "cp")
	body := `{"schema_version":"2","project_id":"p","resources":[{"key":"agent","kind":"Agent","action":"create","spec":{"name":"A","temperature":1e0}},{"key":"prompt","kind":"AgentPrompt","action":"create","parents":{"agent":"${resources.agent.id}"},"depends_on":["agent"],"spec":{"content":"Teach"}}]}`
	run := func(args []string) int {
		out := &bytes.Buffer{}
		a := New(bytes.NewBufferString(body), out, &bytes.Buffer{})
		args = append(args, "--api-url", s.URL, "--project", "p", "--config", filepath.Join(dir, "config"), "--file", "-", "--checkpoint", cp, "--yes")
		return a.Execute(context.Background(), args)
	}
	if code := run([]string{"manifest", "apply"}); code != 10 {
		t.Fatal(code)
	}
	if code := run([]string{"manifest", "apply"}); code != 10 || creates != 1 {
		t.Fatal(code, creates)
	}
	if code := run([]string{"manifest", "reconcile", "agent", "--resource-id", "a"}); code != 0 {
		t.Fatal(code)
	}
	if code := run([]string{"manifest", "apply"}); code != 0 || creates != 1 || prompts != 1 {
		t.Fatal(code, creates, prompts)
	}
}
func TestResourceKindsMatchExecutableConfigurationRoutes(t *testing.T) {
	a := New(nil, nil, nil)
	for _, kind := range manifest.Kinds() {
		for command, n := range map[string]int{kind.Create: len(kind.Parents), kind.Update: len(kind.Parents) + 1} {
			if command == "" {
				continue
			}
			op, ok := a.operation(command)
			if !ok || op.Kind != "http" || op.Secret || op.Effect != "mutation" || len(op.Params) != n || !op.Body {
				t.Fatal(kind, command, op)
			}
		}
	}
}
