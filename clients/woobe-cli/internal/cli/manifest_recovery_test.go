package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestManifestDiffReadsOnlySuppliedPatchFields(t *testing.T) {
	requests := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != "GET" {
			t.Error("diff wrote")
		}
		w.Header().Set("ETag", "rev1")
		_, _ = w.Write([]byte(`{"data":{"id":"a","name":"old","untouched":"keep","password":"old-secret"}}`))
	}))
	defer s.Close()
	body := `{"schema_version":"1","project_id":"p","steps":[{"id":"edit","command":"project agent update","args":["a"],"body":{"name":"new"},"if_match":"rev1"}]}`
	code, v := invoke(t, []string{"manifest", "diff", "--project", "p", "--api-url", s.URL, "--file", "-"}, body)
	if code != 0 || requests != 1 {
		t.Fatal(code, v)
	}
	encoded, _ := json.Marshal(v)
	if strings.Contains(string(encoded), "old-secret") || strings.Contains(string(encoded), "new-secret") {
		t.Fatal("diff leaked secret field")
	}
	rows := v["data"].(map[string]any)["operations"].([]any)
	changes := rows[0].(map[string]any)["changes"].([]any)
	if len(changes) != 1 || changes[0].(map[string]any)["field"] != "name" {
		t.Fatal(changes)
	}
}
func TestManifestDiffConflictAndUnsupportedGetter(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("ETag", "new")
		_, _ = w.Write([]byte(`{"data":{"id":"a","name":"A"}}`))
	}))
	defer s.Close()
	body := `{"schema_version":"1","steps":[{"id":"edit","command":"project agent update","args":["a"],"body":{"name":"A"},"if_match":"old"}]}`
	code, _ := invoke(t, []string{"manifest", "diff", "--api-url", s.URL, "--file", "-"}, body)
	if code != 6 {
		t.Fatal(code)
	}
	body = `{"schema_version":"1","steps":[{"id":"edit","command":"project env set","args":["variable"],"body":{"value":null}}]}`
	code, _ = invoke(t, []string{"manifest", "diff", "--api-url", s.URL, "--project", "p", "--file", "-"}, body)
	if code != 9 {
		t.Fatal(code)
	}
}
func TestReconcileLostCreationResponseAndResumeDependent(t *testing.T) {
	creates := 0
	prompts := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && r.URL.Path == "/ai/agents":
			creates++
			conn, _, _ := w.(http.Hijacker).Hijack()
			_ = conn.Close()
		case r.Method == "GET" && r.URL.Path == "/ai/agents/a":
			w.Header().Set("X-Request-ID", "observed")
			_, _ = w.Write([]byte(`{"data":{"id":"a","project_id":"p","name":"A"}}`))
		case r.Method == "POST" && r.URL.Path == "/ai/agents/a/prompts":
			prompts++
			_, _ = w.Write([]byte(`{"data":{"id":"prompt"}}`))
		default:
			t.Error(r.Method, r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	defer s.Close()
	dir := t.TempDir()
	cp := filepath.Join(dir, "checkpoint")
	config := filepath.Join(dir, "config")
	body := `{"schema_version":"1","project_id":"p","steps":[{"id":"agent","command":"project agent create","body":{"name":"A","project_id":"p"}},{"id":"prompt","command":"project agent prompt create","args":["${steps.agent.id}"],"body":{"content":"Study"},"depends_on":["agent"]}]}`
	run := func(action ...string) int {
		a := New(bytes.NewBufferString(body), &bytes.Buffer{}, &bytes.Buffer{})
		args := append(action, "--file", "-", "--project", "p", "--api-url", s.URL, "--checkpoint", cp, "--config", config, "--yes")
		return a.Execute(context.Background(), args)
	}
	if code := run("manifest", "apply"); code != 10 {
		t.Fatal(code)
	}
	if code := run("manifest", "reconcile", "agent", "--resource-id", "a"); code != 0 {
		t.Fatal(code)
	}
	if code := run("manifest", "apply"); code != 0 {
		t.Fatal(code)
	}
	if creates != 1 || prompts != 1 {
		t.Fatal("write replay or dependent reference lost", creates, prompts)
	}
	b, _ := os.ReadFile(cp)
	var state checkpoint
	_ = json.Unmarshal(b, &state)
	if state.Steps["agent"] != "reconciled" || state.Reconciliations["agent"].RequestID != "observed" {
		t.Fatal(state)
	}
}
func TestCheckpointLockBlocksSecondExecution(t *testing.T) {
	p := filepath.Join(t.TempDir(), "cp")
	release, e := acquireCheckpointLock(p)
	if e != nil {
		t.Fatal(e)
	}
	defer release()
	if _, e = acquireCheckpointLock(p); e == nil {
		t.Fatal("concurrent checkpoint holder accepted")
	}
}
