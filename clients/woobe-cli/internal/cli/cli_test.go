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

func invoke(t *testing.T, args []string, input string) (int, map[string]any) {
	t.Helper()
	out := &bytes.Buffer{}
	a := New(bytes.NewBufferString(input), out, &bytes.Buffer{})
	args = append(args, "--config", filepath.Join(t.TempDir(), "config.json"))
	code := a.Execute(context.Background(), args)
	var v map[string]any
	if e := json.Unmarshal(out.Bytes(), &v); e != nil {
		t.Fatalf("%s: %v", out, e)
	}
	return code, v
}
func TestDiscoveryWithoutCredential(t *testing.T) {
	code, v := invoke(t, []string{"help", "--output", "json"}, "")
	if code != 0 || v["success"] != true {
		t.Fatal(v)
	}
	if len(v["data"].([]any)) < 150 {
		t.Fatal("incomplete command registry")
	}
}
func TestAgentCreateAndPatch(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.URL.Path != "/ai/agents" && r.URL.Path != "/ai/agents/a" {
			t.Error(r.URL.Path)
		}
		var b map[string]any
		_ = json.NewDecoder(r.Body).Decode(&b)
		if r.Method == "PATCH" {
			if _, ok := b["name"]; ok {
				t.Error("destructive patch")
			}
			if x, ok := b["description"]; !ok || x != nil {
				t.Error("missing explicit null")
			}
		}
		_, _ = w.Write([]byte(`{"data":{"id":"a","api_key":"do-not-print"}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"project", "agent", "create", "--api-url", s.URL, "--project", "p", "--file", "-"}, `{"project_id":"p","name":"A"}`)
	if code != 0 {
		t.Fatal(v)
	}
	data := v["data"].(map[string]any)["data"].(map[string]any)
	if data["api_key"] != "[REDACTED]" {
		t.Fatal("secret leak")
	}
	code, v = invoke(t, []string{"project", "agent", "update", "a", "--api-url", s.URL, "--project", "p", "--file", "-"}, `{"description":null}`)
	if code != 0 || n != 2 {
		t.Fatal(v)
	}
}
func TestMissingScopeAndProposedCapability(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++; w.WriteHeader(500) }))
	defer server.Close()
	for _, command := range [][]string{{"project", "agent", "list", "--project", ""}, {"workspace", "authority", "category", "create", "--workspace", "", "--file", "-"}} {
		args := append(command, "--api-url", server.URL)
		code, _ := invoke(t, args, `{}`)
		if code != 2 {
			t.Fatal("missing scope must fail before capability discovery", code)
		}
	}
	if calls != 0 {
		t.Fatal("missing scope reached server")
	}
}
func TestSecretIssuanceRefusesOverwrite(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { n++; _, _ = w.Write([]byte(`{"api_key":"secret"}`)) }))
	defer s.Close()
	p := filepath.Join(t.TempDir(), "key")
	_ = os.WriteFile(p, []byte("existing"), 0600)
	code, _ := invoke(t, []string{"project", "api-key", "create", "--api-url", s.URL, "--project", "p", "--file", "-", "--secret-file", p}, `{}`)
	if code != 2 || n != 0 {
		t.Fatal("issued before destination validation")
	}
}
func TestManifestApplyResume(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { n++; _, _ = w.Write([]byte(`{"data":{"id":"a"}}`)) }))
	defer s.Close()
	d := `{"schema_version":"1","project_id":"p","steps":[{"id":"a","command":"project agent create","body":{"project_id":"p","name":"A"}}]}`
	dir := t.TempDir()
	args := []string{"manifest", "apply", "--api-url", s.URL, "--project", "p", "--yes", "--file", "-", "--checkpoint", filepath.Join(dir, "checkpoint"), "--config", filepath.Join(dir, "config")}
	for i := 0; i < 2; i++ {
		a := New(bytes.NewBufferString(d), &bytes.Buffer{}, &bytes.Buffer{})
		if code := a.Execute(context.Background(), args); code != 0 {
			t.Fatal(code)
		}
	}
	if n != 1 {
		t.Fatal("committed creation duplicated")
	}
}
func TestManifestUnknownBlocksResume(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		h, _, _ := w.(http.Hijacker).Hijack()
		_ = h.Close()
	}))
	defer s.Close()
	d := `{"schema_version":"1","project_id":"p","steps":[{"id":"a","command":"project agent create","body":{}}]}`
	dir := t.TempDir()
	args := []string{"manifest", "apply", "--api-url", s.URL, "--project", "p", "--yes", "--file", "-", "--checkpoint", filepath.Join(dir, "checkpoint"), "--config", filepath.Join(dir, "config")}
	for i := 0; i < 2; i++ {
		a := New(bytes.NewBufferString(d), &bytes.Buffer{}, &bytes.Buffer{})
		if code := a.Execute(context.Background(), args); code != 10 {
			t.Fatal(code)
		}
	}
	if n != 1 {
		t.Fatal("unknown creation replayed")
	}
}
func TestAgentParentFlagAndInvalidUsage(t *testing.T) {
	code, v := invoke(t, []string{"project", "agent", "release", "get", "release", "--agent", "agent", "--dry-run"}, "")
	if code != 0 {
		t.Fatal(v)
	}
	if v["data"].(map[string]any)["path"] != "/ai/agents/agent/releases/release" {
		t.Fatal(v)
	}
	code, _ = invoke(t, []string{"nonexistent"}, "")
	if code != 2 {
		t.Fatal(code)
	}
}
func TestManifestCreationReferences(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if n == 1 {
			_, _ = w.Write([]byte(`{"data":{"id":"agent-a"}}`))
			return
		}
		if r.URL.Path != "/ai/agents/agent-a/prompts" {
			t.Error(r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"data":{"id":"prompt-a"}}`))
	}))
	defer s.Close()
	d := `{"schema_version":"1","project_id":"p","steps":[{"id":"agent","command":"project agent create","body":{"name":"A","project_id":"p"}},{"id":"prompt","command":"project agent prompt create","args":["${steps.agent.id}"],"body":{"content":"Study"},"depends_on":["agent"]}]}`
	out := &bytes.Buffer{}
	a := New(bytes.NewBufferString(d), out, &bytes.Buffer{})
	code := a.Execute(context.Background(), []string{"manifest", "apply", "--api-url", s.URL, "--project", "p", "--yes", "--file", "-", "--checkpoint", filepath.Join(t.TempDir(), "cp"), "--config", filepath.Join(t.TempDir(), "config")})
	if code != 0 || n != 2 {
		t.Fatal(code, out.String())
	}
}
func TestDocumentUpload(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if e := r.ParseMultipartForm(1 << 20); e != nil {
			t.Error(e)
		}
		if r.FormValue("project_id") != "p" || r.FormValue("collection_id") != "c" {
			t.Error("scope missing")
		}
		f, _, e := r.FormFile("file")
		if e != nil {
			t.Error(e)
		} else {
			defer f.Close()
		}
		_, _ = w.Write([]byte(`{"data":{"id":"doc"}}`))
	}))
	defer s.Close()
	p := filepath.Join(t.TempDir(), "document.txt")
	_ = os.WriteFile(p, []byte("content"), 0600)
	code, v := invoke(t, []string{"project", "knowledge", "document", "upload", "--api-url", s.URL, "--project", "p", "--collection", "c", "--document-file", p}, "")
	if code != 0 {
		t.Fatal(v)
	}
}
