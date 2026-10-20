package cli

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestPackageUUIDReferencesAreCaseInsensitive(t *testing.T) {
	for _, kind := range []string{"Agent", "Network"} {
		t.Run(kind, func(t *testing.T) {
			c, err := devworkspace.Create(t.TempDir(), ".woobe", "")
			if err != nil {
				t.Fatal(err)
			}
			uid := "01a0a033-5820-770c-854b-902864857273"
			native := "01a00d4a-fa75-7629-a2c6-773c25c6e2ef"
			c.Resources = []devworkspace.Resource{{UID: uid, Kind: kind, Key: "support", Alias: "support", Path: "artifacts/support"}}
			state := &devworkspace.State{Bindings: map[string]devworkspace.Binding{uid: {ResourceID: native}}}
			for _, reference := range []string{uid, native, strings.ToUpper(uid), strings.ToUpper(native)} {
				resource, err := developmentReference(c, state, strings.ToLower(kind), reference, "")
				if err != nil || resource.UID != uid {
					t.Fatal("registered UUID was not resolved", reference, err)
				}
			}
			if _, err := developmentReference(c, state, strings.ToLower(kind), "@SUPPORT", ""); err == nil {
				t.Fatal("UUID normalization changed alias matching")
			}
		})
	}
}

func TestManagedDiffIncludesDependencyChangesWithoutNetwork(t *testing.T) {
	t.Chdir(t.TempDir())
	c, err := devworkspace.Create(".", ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	uid, _ := devworkspace.NewID()
	modelUID, _ := devworkspace.NewID()
	c.Resources = []devworkspace.Resource{{UID: uid, Kind: "Agent", Key: "support", Alias: "support", Path: "agents/support"}, {UID: modelUID, Kind: "Model", Key: "chat", Alias: "chat", Path: "models/chat"}}
	if err := c.Save(); err != nil {
		t.Fatal(err)
	}
	documents := map[string]map[string]any{
		"agents/support/agent.yaml": {"format": "woobe-package", "schema_version": "1.0", "kind": "Agent", "metadata": map[string]any{"key": "support", "name": "Support"}, "spec": map[string]any{"model": map[string]any{"primary": map[string]any{"ref": "chat"}}, "legacy_system_prompt": "Help"}},
		"models/chat/model.yaml":    {"format": "woobe-package", "schema_version": "1.0", "kind": "Model", "metadata": map[string]any{"key": "chat", "name": "Chat"}, "spec": map[string]any{"provider": "custom", "model": "fake", "credential": map[string]any{"ref": "primary"}}},
	}
	for name, document := range documents {
		path := filepath.Join(c.RootPath(), filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
			t.Fatal(err)
		}
		data, _ := devworkspace.Encode(document)
		if err := os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}
	}
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++; t.Error("local command called server") }))
	defer server.Close()
	state, err := c.ReadState(server.URL, "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Bindings[uid] = devworkspace.Binding{ResourceID: "native-agent", Revision: 7, Base: documents["agents/support/agent.yaml"]}
	state.Bindings[modelUID] = devworkspace.Binding{ResourceID: "native-model", Revision: "revision", Base: documents["models/chat/model.yaml"]}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	documents["models/chat/model.yaml"]["spec"].(map[string]any)["model"] = "changed"
	data, _ := devworkspace.Encode(documents["models/chat/model.yaml"])
	if err := os.WriteFile(filepath.Join(c.RootPath(), "models/chat/model.yaml"), data, 0600); err != nil {
		t.Fatal(err)
	}
	code, result := invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "agent", "@support", "diff", "--output", "json"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
	response := result["data"].(map[string]any)
	if response["changed"] != true || !strings.Contains(response["changes"].([]any)[0].(map[string]any)["path"].(string), "/dependencies/Model/chat/") {
		t.Fatal(response)
	}
	unregistered := filepath.Join(c.RootPath(), "agents/unregistered/agent.yaml")
	if err := os.MkdirAll(filepath.Dir(unregistered), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(unregistered, []byte("broken: ["), 0600); err != nil {
		t.Fatal(err)
	}
	code, bulk := invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "resources", "diff", "--output", "json"}, "")
	if code != 0 || bulk["data"].(map[string]any)["roots"] != float64(1) {
		t.Fatal(code, bulk)
	}
	if requests != 0 {
		t.Fatal("local diff made network requests")
	}
	code, _ = invoke(t, []string{"agent", "@support", "push", "--env", "production"}, "")
	if code != 2 {
		t.Fatal("push accepted a non-Draft environment")
	}
}
