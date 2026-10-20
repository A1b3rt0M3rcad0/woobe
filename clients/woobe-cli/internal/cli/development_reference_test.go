package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestCanonicalAndReferenceFirstAliasesUseScopedNativeBindings(t *testing.T) {
	t.Chdir(t.TempDir())
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	requests := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests = append(requests, r.URL.Path)
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": []any{}})
	}))
	defer server.Close()
	c, err := devworkspace.Create(".", ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	uid, _ := devworkspace.NewID()
	c.Resources = []devworkspace.Resource{{UID: uid, Kind: "Agent", Key: "support", Alias: "support", Path: "agents/support"}}
	if err := c.Save(); err != nil {
		t.Fatal(err)
	}
	state, err := c.ReadState(server.URL, "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Bindings[uid] = devworkspace.Binding{ResourceID: "native-agent"}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	for _, command := range [][]string{{"agent", "@support", "release", "list"}, {"agent", "release", "list", "@support"}, {"agent", "@support", "get"}} {
		args := append([]string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}, command...)
		code, response := invoke(t, args, "")
		if code != 0 {
			t.Fatal(command, code, response)
		}
	}
	if len(requests) != 3 || requests[0] != "/ai/agents/native-agent/releases" || requests[1] != requests[0] || requests[2] != "/ai/agents/native-agent" {
		t.Fatal(requests)
	}
	code, _ := invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "other-project", "agent", "@support", "get", "--output", "json"}, "")
	if code != 2 || len(requests) != 3 {
		t.Fatal("cross-project alias sent a request", code, requests)
	}
}

func TestParentAliasesUseCapturedParentIdentity(t *testing.T) {
	t.Chdir(t.TempDir())
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	c, err := devworkspace.Create(".", ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	skillUID, _ := devworkspace.NewID()
	knowledgeUID, _ := devworkspace.NewID()
	c.Resources = []devworkspace.Resource{
		{UID: skillUID, Kind: "Skill", Key: "procedure", Alias: "procedure", Path: "skills/procedure"},
		{UID: knowledgeUID, Kind: "Knowledge", Key: "policy", Alias: "policy", Path: "knowledge/policy"},
	}
	if err := c.Save(); err != nil {
		t.Fatal(err)
	}
	state, err := c.ReadState("http://localhost:8000", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Bindings[skillUID] = devworkspace.Binding{ResourceID: "native-version", Identifiers: map[string]string{"skill_id": "native-skill"}}
	state.Bindings[knowledgeUID] = devworkspace.Binding{ResourceID: "native-snapshot", Identifiers: map[string]string{"collection_id": "native-collection"}}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	a := New(nil, nil, nil)
	a.APIURL, a.Workspace, a.Project = "http://localhost:8000", "workspace", "project"
	for _, item := range []struct{ parameter, reference, want string }{
		{"skill_id", "@procedure", "native-skill"},
		{"skill_version_id", "@procedure", "native-version"},
		{"collection_id", "@policy", "native-collection"},
		{"snapshot_id", "@policy", "native-snapshot"},
	} {
		got, err := a.nativeReference(item.parameter, item.reference)
		if err != nil || got != item.want {
			t.Fatal(item, got, err)
		}
	}
}

func TestPromptVersionAliasUsesTheTypedCapturedVersion(t *testing.T) {
	t.Chdir(t.TempDir())
	t.Setenv("WOOBE_CONTROL_KEY", "test")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/ai/agents/native-agent/prompts/native-prompt" {
			t.Error(r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"id": "native-prompt"}})
	}))
	defer server.Close()
	c, _ := devworkspace.Create(".", ".woobe", "")
	agent, _ := devworkspace.NewID()
	prompt, _ := devworkspace.NewID()
	c.Resources = []devworkspace.Resource{{UID: agent, Kind: "Agent", Key: "support", Alias: "support", Path: "agents/support"}, {UID: prompt, Kind: "Prompt", Key: "instructions", Alias: "instructions", Path: "prompts/instructions"}}
	if err := c.Save(); err != nil {
		t.Fatal(err)
	}
	state, _ := c.ReadState(server.URL, "workspace", "project")
	state.Bindings[agent] = devworkspace.Binding{ResourceID: "native-agent"}
	state.Bindings[prompt] = devworkspace.Binding{ResourceID: "native-prompt"}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	code, result := invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "agent", "@support", "prompt", "get", "@instructions", "--output", "json"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
}
