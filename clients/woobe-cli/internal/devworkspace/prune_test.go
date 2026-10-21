package devworkspace

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func registryWithAgent(t *testing.T) (*Config, Resource, Resource, Resource) {
	t.Helper()
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	add := func(kind, alias string, spec map[string]any) Resource {
		r, err := c.Add(kind, alias, "", map[string]any{"kind": kind, "metadata": map[string]any{"name": alias}, "spec": spec}, nil, false)
		if err != nil {
			t.Fatal(err)
		}
		return r
	}
	p := add("Provider", "primary", map[string]any{"provider": "custom"})
	m := add("Model", "chat", map[string]any{"provider_ref": p.Key, "model": "fake"})
	a := add("Agent", "support", map[string]any{"model": map[string]any{"primary": map[string]any{"ref": m.Key}}})
	return c, p, m, a
}

func removeDescriptor(t *testing.T, c *Config, r Resource) {
	t.Helper()
	if err := os.Remove(filepath.Join(c.RootPath(), descriptor(r))); err != nil {
		t.Fatal(err)
	}
}

func TestStaleRegistryReportsMissingDescriptorAndRecovery(t *testing.T) {
	c, _, m, _ := registryWithAgent(t)
	removeDescriptor(t, c, m)
	_, err := LoadGraph(c)
	if err == nil {
		t.Fatal("missing descriptor accepted")
	}
	for _, expected := range []string{m.Key, descriptor(m), ".woobe-config", "is missing", "resources prune --dry-run"} {
		if !strings.Contains(err.Error(), expected) {
			t.Fatalf("diagnostic missing %q: %v", expected, err)
		}
	}
}

func TestUnregisterAbsentAgentKeepsBindingsAndOtherFiles(t *testing.T) {
	c, _, m, a := registryWithAgent(t)
	state, err := c.ReadState("http://local", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Bindings[a.UID] = Binding{ResourceID: "native-agent", Revision: 7}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	stateFile := c.StatePath(state.API, state.Workspace, state.Project)
	stateBefore, _ := os.ReadFile(stateFile)
	modelBefore, _ := os.ReadFile(filepath.Join(c.RootPath(), descriptor(m)))
	configBefore, _ := os.ReadFile(c.File)
	removeDescriptor(t, c, a)
	if err := c.Unregister("Agent", "@support", true); err != nil {
		t.Fatal(err)
	}
	preview, _ := os.ReadFile(c.File)
	if !bytes.Equal(preview, configBefore) || len(c.Resources) != 3 {
		t.Fatal("preview mutated registry")
	}
	if err := c.Unregister("Agent", "@support", false); err != nil {
		t.Fatal(err)
	}
	if len(c.Resources) != 2 {
		t.Fatal("stale entry retained")
	}
	if _, err := LoadGraph(c); err != nil {
		t.Fatal(err)
	}
	stateAfter, _ := os.ReadFile(stateFile)
	modelAfter, _ := os.ReadFile(filepath.Join(c.RootPath(), descriptor(m)))
	if !bytes.Equal(stateBefore, stateAfter) || !bytes.Equal(modelBefore, modelAfter) {
		t.Fatal("cleanup changed bindings or author files")
	}
}

func TestPruneMultipleDeletedArtifactsKeepsPresentFilesAndPrivateState(t *testing.T) {
	c, p, m, a := registryWithAgent(t)
	state, err := c.ReadState("http://local", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Bindings[a.UID] = Binding{ResourceID: "native-agent", Revision: 7}
	state.Bindings[m.UID] = Binding{ResourceID: "native-model", Revision: "model-revision"}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	stateFile := c.StatePath(state.API, state.Workspace, state.Project)
	stateBefore, _ := os.ReadFile(stateFile)
	providerBefore, _ := os.ReadFile(filepath.Join(c.RootPath(), descriptor(p)))
	configBefore, _ := os.ReadFile(c.File)
	// A present, unregistered file and an unused Provider are not stale entries.
	notes := filepath.Join(c.RootPath(), "agents", "notes.txt")
	if err := os.WriteFile(notes, []byte("keep"), 0600); err != nil {
		t.Fatal(err)
	}
	removeDescriptor(t, c, a)
	if err := os.RemoveAll(filepath.Join(c.RootPath(), m.Path)); err != nil {
		t.Fatal(err)
	}
	missing, err := c.PruneMissing(true)
	if err != nil || len(missing) != 2 {
		t.Fatal(missing, err)
	}
	preview, _ := os.ReadFile(c.File)
	if !bytes.Equal(preview, configBefore) || len(c.Resources) != 3 {
		t.Fatal("preview changed registry")
	}
	if _, err := c.PruneMissing(false); err != nil {
		t.Fatal(err)
	}
	loaded, err := Load(c.File)
	if err != nil || !reflect.DeepEqual(loaded.Resources, []Resource{p}) {
		t.Fatal(loaded, err)
	}
	stateAfter, _ := os.ReadFile(stateFile)
	providerAfter, _ := os.ReadFile(filepath.Join(c.RootPath(), descriptor(p)))
	if !bytes.Equal(stateBefore, stateAfter) || !bytes.Equal(providerBefore, providerAfter) {
		t.Fatal("prune changed bindings or present descriptor")
	}
	if content, _ := os.ReadFile(notes); string(content) != "keep" {
		t.Fatal("prune deleted notes")
	}
	before, _ := os.ReadFile(c.File)
	if empty, err := c.PruneMissing(false); err != nil || len(empty) != 0 {
		t.Fatal(empty, err)
	}
	after, _ := os.ReadFile(c.File)
	if !bytes.Equal(before, after) {
		t.Fatal("no-op prune changed config")
	}
}

func TestPruneAndUnregisterBlockLiveConsumersOfDeletedModel(t *testing.T) {
	c, _, m, _ := registryWithAgent(t)
	removeDescriptor(t, c, m)
	before, _ := os.ReadFile(c.File)
	for _, dryRun := range []bool{true, false} {
		if _, err := c.PruneMissing(dryRun); err == nil || !strings.Contains(err.Error(), "references missing resource chat") {
			t.Fatal("pruned dependency with live consumer", err)
		}
		if err := c.Unregister("Model", "@chat", dryRun); err == nil {
			t.Fatal("unregistered dependency with live consumer")
		}
	}
	after, _ := os.ReadFile(c.File)
	if !bytes.Equal(before, after) || len(c.Resources) != 3 {
		t.Fatal("rejected cleanup modified registry")
	}
}

func TestPruneRejectsCorruptLinkedAndOversizeDescriptors(t *testing.T) {
	for _, scenario := range []string{"corrupt", "symlink", "hardlink", "oversize"} {
		t.Run(scenario, func(t *testing.T) {
			c, p, _, a := registryWithAgent(t)
			before, _ := os.ReadFile(c.File)
			removeDescriptor(t, c, a)
			file := filepath.Join(c.RootPath(), descriptor(p))
			switch scenario {
			case "corrupt":
				if err := os.WriteFile(file, []byte("broken: ["), 0600); err != nil {
					t.Fatal(err)
				}
			case "oversize":
				if err := os.WriteFile(file, bytes.Repeat([]byte("x"), (8<<20)+1), 0600); err != nil {
					t.Fatal(err)
				}
			case "symlink", "hardlink":
				outside := filepath.Join(t.TempDir(), "provider.yaml")
				content, _ := os.ReadFile(file)
				if err := os.WriteFile(outside, content, 0600); err != nil {
					t.Fatal(err)
				}
				if err := os.Remove(file); err != nil {
					t.Fatal(err)
				}
				link := os.Link
				if scenario == "symlink" {
					link = os.Symlink
				}
				if err := link(outside, file); err != nil {
					t.Skip("native OS cannot create link", err)
				}
			}
			for _, dryRun := range []bool{true, false} {
				if _, err := c.PruneMissing(dryRun); err == nil {
					t.Fatal("unsafe descriptor treated as absent")
				}
			}
			after, _ := os.ReadFile(c.File)
			if !bytes.Equal(before, after) || len(c.Resources) != 3 {
				t.Fatal("failure changed registry")
			}
		})
	}
}

func TestLegacyJSONFormattedYAMLRemainsReadable(t *testing.T) {
	c, _, _, _ := registryWithAgent(t)
	g, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	for _, node := range g.Nodes {
		data, err := json.Marshal(node.Document)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(g.Path(node), data, 0600); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := LoadGraph(c); err != nil {
		t.Fatal("legacy descriptor cannot be read", err)
	}
	if missing, err := c.PruneMissing(false); err != nil || len(missing) != 0 {
		t.Fatal("legacy files incorrectly pruned", missing, err)
	}
}
