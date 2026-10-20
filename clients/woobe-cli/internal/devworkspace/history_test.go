package devworkspace

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestRevisionKeepsOriginAndImmutableLineage(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := &State{Requirements: map[string]any{"credentials": []any{map[string]any{"ref": "primary", "provider": "custom"}}, "project_environment": []any{map[string]any{"key": "PACKAGE_TEST_TOKEN", "kind": "secret"}}, "secrets": []any{map[string]any{"ref": "package-tool-token"}}}, API: "https://woobe.test", Workspace: "w", Project: "p", Bindings: map[string]Binding{r.UID: {ResourceID: "native", SnapshotID: "release", SourceKind: "release"}}}
	if err := c.BootstrapTracking(r, state, "production"); err != nil {
		t.Fatal(err)
	}
	a, err := g.CreateRevision(r, state, "first", nil)
	if err != nil {
		t.Fatal(err)
	}
	b, err := g.CreateRevision(r, state, "second", nil)
	if err != nil {
		t.Fatal(err)
	}
	if a.ID == b.ID || a.DefinitionDigest != b.DefinitionDigest || a.RecordDigest == b.RecordDigest || !reflect.DeepEqual(b.Parents, []string{a.ID}) {
		t.Fatal("lineage or deduplication lost", a, b)
	}
	tracking, err := c.ReadTracking(r)
	if err != nil || tracking.Working != b.ID || tracking.Origin.Environment != "production" || tracking.Origin.SnapshotID != "release" {
		t.Fatal("origin changed", tracking, err)
	}
	if _, err = c.ReadRevision(r, a.ID); err != nil {
		t.Fatal(err)
	}
	dir, _ := c.historyDirectory(r)
	file := filepath.Join(dir, "revisions", a.ID+".yaml")
	data, err := os.ReadFile(file)
	if err != nil {
		t.Fatal(err)
	}
	if err = c.immutableWrite(file, append(data, []byte("changed: true\n")...)); err == nil {
		t.Fatal("immutable revision overwritten")
	}
	if err = os.WriteFile(file, []byte(strings.Replace(string(data), "first", "tampered", 1)), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = c.ReadRevision(r, a.ID); err == nil {
		t.Fatal("tampered record accepted")
	}
}

func TestDefinitionDigestTracksDependenciesNotAliases(t *testing.T) {
	_, g := completeGraph(t)
	before, err := g.DefinitionDigests("support")
	if err != nil {
		t.Fatal(err)
	}
	node := g.Nodes["support"]
	node.Resource.Alias = "renamed"
	after, err := g.DefinitionDigests("support")
	if err != nil || before["support"] != after["support"] {
		t.Fatal("alias changed executable definition", err)
	}
	g.Nodes["support-skill"].Document["metadata"].(map[string]any)["description"] = "changed dependency"
	after, err = g.DefinitionDigests("support")
	if err != nil || before["support"] == after["support"] {
		t.Fatal("dependency change omitted", err)
	}
}

func TestMoveKeepsTrackingAndImmutableHistory(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := &State{Requirements: map[string]any{"credentials": []any{map[string]any{"ref": "primary", "provider": "custom"}}, "project_environment": []any{map[string]any{"key": "PACKAGE_TEST_TOKEN", "kind": "secret"}}, "secrets": []any{map[string]any{"ref": "package-tool-token"}}}, Bindings: map[string]Binding{}}
	revision, err := g.CreateRevision(r, state, "before move", nil)
	if err != nil {
		t.Fatal(err)
	}
	before, err := c.ReadTracking(r)
	if err != nil {
		t.Fatal(err)
	}
	if err = c.Move("Agent", "@"+r.Alias, "agents/moved", false); err != nil {
		t.Fatal(err)
	}
	moved, err := c.Resolve("Agent", "@"+r.Alias)
	if err != nil {
		t.Fatal(err)
	}
	after, err := c.ReadTracking(*moved)
	if err != nil || !reflect.DeepEqual(before, after) {
		t.Fatal(after, err)
	}
	if _, err = c.ReadRevision(*moved, revision.ID); err != nil {
		t.Fatal(err)
	}
	verified, err := c.VerifyHistory(*moved)
	if err != nil || verified["objects_available"] != true {
		t.Fatal(verified, err)
	}
	graph, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	bundle, _, err := graph.Compile(moved.Key, state.Requirements, state.Credentials)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	definition, digests, err := PortableDefinition(bundle)
	if err != nil || definition != revision.DefinitionDigest {
		t.Fatal("move changed semantic definition", digests, err)
	}
}
