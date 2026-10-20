package devworkspace

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestCloneAgentOwnsIndependentPromptAndContractAndOwnedTool(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	for _, kind := range []string{"Prompt", "Contract", "Tool"} {
		key := strings.ToLower(kind)
		_, err = c.Add(kind, key, "", map[string]any{"kind": kind, "metadata": map[string]any{"name": key}, "spec": map[string]any{}}, nil, false)
		if err != nil {
			t.Fatal(err)
		}
	}
	a, err := c.Add("Agent", "support", "", map[string]any{"kind": "Agent", "metadata": map[string]any{"name": "Support"}, "spec": map[string]any{"prompt_ref": "prompt", "output": map[string]any{"contract_ref": "contract"}, "tools": []any{map[string]any{"ref": "tool"}}}}, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	tool, _ := c.Resolve("Tool", "@tool")
	state := &State{Bindings: map[string]Binding{a.UID: {ResourceID: "original-agent"}, tool.UID: {OwnerAgentID: "original-agent"}}}
	cloned, err := c.CloneWithState("Agent", "@support", "copy", "", state, false)
	if err != nil {
		t.Fatal(err)
	}
	graph, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	refs := packagefmt.References(graph.Nodes[cloned.Key].Document)
	if packagefmt.Object(graph.Nodes[cloned.Key].Document["metadata"])["name"] != "Support" || cloned.Alias != "copy" || cloned.UID == a.UID {
		t.Fatal("local alias replaced presentation name or logical identity", cloned)
	}
	for _, ref := range refs {
		if !strings.HasPrefix(ref.Key, "copy-") {
			t.Fatal("owned artifact shared", ref)
		}
		if graph.Nodes[ref.Key].Resource.UID == graph.Nodes[strings.TrimPrefix(ref.Key, "copy-")].Resource.UID {
			t.Fatal("clone retained owned UID")
		}
	}
	if len(refs) != 3 || len(c.Resources) != 8 {
		t.Fatal("incomplete cloned closure")
	}
}

func TestLocalCreateCloneShareDependenciesAndUnregisterNeverDeletes(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	provider := map[string]any{"kind": "Provider", "metadata": map[string]any{"name": "OpenAI"}, "spec": map[string]any{"provider": "openai", "credential_ref": "native-credential"}}
	p, err := c.Add("Provider", "openai", "", provider, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	model := map[string]any{"kind": "Model", "metadata": map[string]any{"name": "Chat"}, "spec": map[string]any{"provider_ref": "openai", "model": "gpt"}}
	m, err := c.Add("Model", "chat", "", model, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	agent := map[string]any{"kind": "Agent", "metadata": map[string]any{"name": "Support"}, "spec": map[string]any{"model": map[string]any{"primary": map[string]any{"ref": "chat"}}}}
	a, err := c.Add("Agent", "support", "", agent, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	cloned, err := c.Clone("Agent", "@support", "support-copy", "", false)
	if err != nil {
		t.Fatal(err)
	}
	if cloned.UID == a.UID || cloned.Frozen {
		t.Fatal("clone retained source identity")
	}
	g, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	closure, err := g.Closure(cloned.Key)
	if err != nil || len(closure) != 3 || closure[0].Resource.UID != p.UID || closure[1].Resource.UID != m.UID {
		t.Fatal("clone duplicated dependencies", closure, err)
	}
	before, _ := os.ReadFile(c.File)
	if err := c.Unregister("Model", "@chat", false); err == nil {
		t.Fatal("removed a consumed dependency")
	}
	after, _ := os.ReadFile(c.File)
	if string(before) != string(after) {
		t.Fatal("failed operation changed registry")
	}
	if err := c.Unregister("Agent", "@support-copy", false); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(c.RootPath(), descriptor(cloned))); err != nil {
		t.Fatal("unregister deleted author file")
	}
}

func TestLocalManagementRejectsInvalidRefsOverwriteAndEscapeBeforeWrites(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	document := map[string]any{"kind": "Model", "metadata": map[string]any{"name": "Chat"}, "spec": map[string]any{"provider_ref": "missing", "model": "gpt"}}
	before, _ := os.ReadFile(c.File)
	if _, err := c.Add("Model", "chat", "", document, nil, false); err == nil {
		t.Fatal("allowed missing provider")
	}
	if _, err := c.Add("Model", "chat", "../escape", document, nil, false); err == nil {
		t.Fatal("allowed escaping destination")
	}
	after, _ := os.ReadFile(c.File)
	if string(before) != string(after) {
		t.Fatal("invalid create changed config")
	}
	provider := map[string]any{"kind": "Provider", "metadata": map[string]any{"name": "Public"}, "spec": map[string]any{"provider": "custom", "credential_ref": "connection"}}
	r, err := c.Add("Provider", "primary", "", provider, nil, true)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(c.RootPath(), descriptor(r))); !os.IsNotExist(err) {
		t.Fatal("dry run wrote files")
	}
	if _, err := c.Add("Provider", "primary", "", provider, nil, false); err != nil {
		t.Fatal(err)
	}
	if _, err := c.Add("Provider", "primary", "", provider, nil, false); err == nil {
		t.Fatal("overwrote existing artifact")
	}
}

func TestMoveAndAliasKeepUIDAndNativeBindingAndLeaveUnregisteredFiles(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	doc := map[string]any{"kind": "Provider", "metadata": map[string]any{"name": "Public"}, "spec": map[string]any{"provider": "custom", "credential_ref": "connection"}}
	r, err := c.Add("Provider", "primary", "", doc, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	state, err := c.ReadState("http://localhost", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Bindings[r.UID] = Binding{ResourceID: "native", Revision: 7}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	unrelated := filepath.Join(c.RootPath(), r.Path, "notes.txt")
	if err := os.WriteFile(unrelated, []byte("unregistered"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := c.Move("Provider", "@primary", "providers/new-location", false); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(c.RootPath(), descriptor(r))); !os.IsNotExist(err) {
		t.Fatal("move left the old descriptor")
	}
	if _, err := os.Stat(unrelated); err != nil {
		t.Fatal("move deleted unrelated file")
	}
	if err := c.Alias("Provider", "@primary", "next", false); err != nil {
		t.Fatal(err)
	}
	newResource, err := c.Resolve("Provider", "@next")
	if err != nil || newResource.UID != r.UID || newResource.Key != r.Key {
		t.Fatal("move/alias changed logical identity", err)
	}
	state, err = c.ReadState("http://localhost", "workspace", "project")
	if err != nil || state.Bindings[r.UID].ResourceID != "native" {
		t.Fatal("move changed native binding", err)
	}
	if _, err := LoadGraph(c); err != nil {
		t.Fatal(err)
	}
}
