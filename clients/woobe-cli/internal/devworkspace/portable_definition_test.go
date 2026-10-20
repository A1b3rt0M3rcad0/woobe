package devworkspace

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func TestPortableDefinitionSharedPythonFixture(t *testing.T) {
	raw, err := os.ReadFile("../../testdata/package/shared/complete.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Files map[string]string `json:"files"`
	}
	if err = json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	for name, content := range fixture.Files {
		target := filepath.Join(root, filepath.FromSlash(name))
		if err = os.MkdirAll(filepath.Dir(target), 0700); err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(target, []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	bundle, err := packagebundle.Load(root, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	digest, components, err := PortableDefinition(bundle)
	if err != nil {
		t.Fatal(err)
	}
	raw, err = os.ReadFile("../../testdata/asac-portable-definition.json")
	if err != nil {
		t.Fatal(err)
	}
	var expected struct {
		Definition string            `json:"definition_digest"`
		Components map[string]string `json:"components"`
	}
	if err = json.Unmarshal(raw, &expected); err != nil {
		t.Fatal(err)
	}
	if digest != expected.Definition || !reflect.DeepEqual(components, expected.Components) {
		t.Fatalf("Go/Python disagreement: %s %#v", digest, components)
	}
	// Physical names and credential aliases are transport details, not execution.
	rename := map[string]string{}
	for key := range bundle.Graph.Components {
		rename[key] = "renamed-" + key
	}
	newComponents := map[string]map[string]any{}
	newPaths := map[string]string{}
	for key, document := range bundle.Graph.Components {
		RewriteReferences(document, rename)
		document["metadata"].(map[string]any)["key"] = rename[key]
		if document["kind"] == "Model" {
			document["spec"].(map[string]any)["credential"].(map[string]any)["ref"] = "new-credential-alias"
		}
		newComponents[rename[key]] = document
		newPaths[rename[key]] = bundle.Graph.Paths[key]
	}
	for i, key := range bundle.Graph.Order {
		bundle.Graph.Order[i] = rename[key]
	}
	bundle.Graph.Components, bundle.Graph.Paths = newComponents, newPaths
	spec := bundle.Graph.Manifest["spec"].(map[string]any)
	entry := spec["entrypoint"].(map[string]any)
	entry["ref"] = rename[entry["ref"].(string)]
	spec["requires"].(map[string]any)["credentials"].([]any)[0].(map[string]any)["ref"] = "new-credential-alias"
	changed, _, err := PortableDefinition(bundle)
	if err != nil || changed != digest {
		t.Fatalf("Transport identity changed definition: %s %v", changed, err)
	}
}

func TestRevisionExcludesUnrelatedProviders(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := &State{Requirements: map[string]any{"credentials": []any{map[string]any{"ref": "primary", "provider": "custom"}}, "project_environment": []any{map[string]any{"key": "PACKAGE_TEST_TOKEN", "kind": "secret"}}, "secrets": []any{map[string]any{"ref": "package-tool-token"}}}, Bindings: map[string]Binding{}}
	first, err := g.CreateRevision(r, state, "first", nil)
	if err != nil {
		t.Fatal(err)
	}
	_ = c
	// A detached provider cannot appear among captured component identities.
	g.Nodes["unrelated"] = &Node{Resource: Resource{Key: "unrelated", UID: "a30d3c2f-37e2-4715-a956-a68028524754", Kind: "Provider"}, Document: map[string]any{"spec": map[string]any{"provider": "custom"}}}
	second, err := g.CreateRevision(r, state, "second", nil)
	if err != nil {
		t.Fatal(err)
	}
	if first.DefinitionDigest != second.DefinitionDigest || !reflect.DeepEqual(first.Components, second.Components) {
		t.Fatal("Unrelated provider changed revision closure")
	}
}
