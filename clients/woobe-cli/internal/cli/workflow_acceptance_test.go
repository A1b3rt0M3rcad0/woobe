package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

// This is a client contract workflow fixture, not deployed Woobe authorization evidence.
func TestAgentNetworkConfigurationAndPublicationIsolation(t *testing.T) {
	writes := []string{}
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writes = append(writes, r.Method+" "+r.URL.Path)
		if r.URL.Path == "/ai/agents/a/releases/r/promote" {
			if r.Header.Get("Authorization") != "Bearer publisher" {
				w.WriteHeader(403)
				return
			}
			_, _ = w.Write([]byte(`{"data":{"id":"r","state":"published"}}`))
			return
		}
		id := "x"
		switch r.URL.Path {
		case "/ai/agents":
			id = "a"
		case "/ai/agents/a/prompts":
			id = "prompt"
		case "/ai/agents/a/contracts":
			id = "contract"
		case "/ai/agents/a/model-configs":
			id = "model"
		case "/network/projects/p/networks":
			id = "n"
		case "/network/n/draft":
			id = "draft"
		default:
			t.Error("unexpected route", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"id": id}})
	}))
	defer s.Close()
	dir := t.TempDir()
	manifest := `{"schema_version":"1","project_id":"p","steps":[{"id":"agent","command":"project agent create","body":{"project_id":"p","name":"A"}},{"id":"prompt","command":"project agent prompt create","args":["${steps.agent.id}"],"depends_on":["agent"],"body":{"content":"Teach"}},{"id":"contract","command":"project agent contract create","args":["${steps.agent.id}"],"depends_on":["agent"],"body":{"name":"contract"}},{"id":"model","command":"project agent model-config create","args":["${steps.agent.id}"],"depends_on":["agent"],"body":{"name":"model"}},{"id":"network","command":"project network create","body":{"name":"N"}},{"id":"draft","command":"project network draft update","args":["${steps.network.id}"],"depends_on":["network","agent"],"body":{"agent_id":"${steps.agent.id}"}}]}`
	execute := func(input string, args []string) int {
		a := New(bytes.NewBufferString(input), &bytes.Buffer{}, &bytes.Buffer{})
		args = append(args, "--config", filepath.Join(dir, "config"), "--api-url", s.URL, "--project", "p")
		return a.Execute(context.Background(), args)
	}
	t.Setenv("WOOBE_CONTROL_KEY", "editor")
	args := []string{"manifest", "apply", "--file", "-", "--yes", "--checkpoint", filepath.Join(dir, "checkpoint")}
	if code := execute(manifest, args); code != 0 {
		t.Fatal(code)
	}
	if len(writes) != 6 {
		t.Fatal(writes)
	}
	if execute(manifest, args) != 0 || len(writes) != 6 {
		t.Fatal("configuration replayed")
	}
	t.Setenv("WOOBE_CONTROL_KEY", "different-editor")
	if code := execute(manifest, args); code != 6 {
		t.Fatal("checkpoint identity not enforced", code)
	}
	publish := []string{"project", "agent", "release", "promote", "r", "--agent", "a", "--file", "-", "--yes"}
	t.Setenv("WOOBE_CONTROL_KEY", "editor")
	if code := execute(`{}`, publish); code != 4 {
		t.Fatal("denial hidden", code)
	}
	t.Setenv("WOOBE_CONTROL_KEY", "publisher")
	if code := execute(`{}`, publish); code != 0 {
		t.Fatal("explicit publication failed", code)
	}
}
func TestManifestExportMappingsExist(t *testing.T) {
	a := New(nil, nil, nil)
	for _, cmd := range []string{"project agent get", "project network get", "project skill version get", "project knowledge collection get", "project surface get"} {
		op, ok := a.operation(cmd)
		if !ok || op.Method != "GET" || len(op.Params) != 1 {
			t.Fatal(cmd)
		}
	}
}
