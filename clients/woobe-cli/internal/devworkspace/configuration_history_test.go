package devworkspace

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

type configurationFixture struct {
	Files      map[string]string `json:"files"`
	Definition string            `json:"definition_digest"`
	Scope      string            `json:"definition_digest_scope"`
	Components map[string]string `json:"components"`
	Providers  map[string]string `json:"providers"`
}

func configurationBundle(t *testing.T) (*packagebundle.Bundle, configurationFixture) {
	t.Helper()
	raw, err := os.ReadFile("../../testdata/asac-portable-definition-v2.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture configurationFixture
	if err = json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	for name, value := range fixture.Files {
		if err = os.WriteFile(filepath.Join(dir, name), []byte(value), 0600); err != nil {
			t.Fatal(err)
		}
	}
	bundle, err := packagebundle.Load(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = bundle.Close() })
	return bundle, fixture
}

func TestConfigurationDefinitionMatchesPythonAndExcludesPresentation(t *testing.T) {
	bundle, expected := configurationBundle(t)
	digest, components, err := PortableDefinition(bundle)
	if err != nil {
		t.Fatal(err)
	}
	providers, err := PortableProviderDigests(bundle)
	if err != nil {
		t.Fatal(err)
	}
	if digest != expected.Definition || DefinitionScope(bundle.Graph.Manifest) != expected.Scope || !reflect.DeepEqual(components, expected.Components) || !reflect.DeepEqual(providers, expected.Providers) {
		t.Fatal("Python/Go definition mismatch", digest, components, providers)
	}
	spec := packagefmt.Object(bundle.Graph.Manifest["spec"])
	connections := packagefmt.Object(spec["connections"])
	connection := packagefmt.Object(connections["primary"])
	connections["renamed"] = connection
	delete(connections, "primary")
	connection["name"] = "Other display"
	packagefmt.Object(packagefmt.Object(bundle.Graph.Components["model"]["spec"])["credential"])["ref"] = "renamed"
	declarations := packagefmt.List(packagefmt.Object(spec["configuration"])["keys"])
	declarations[0], declarations[1] = declarations[1], declarations[0]
	got, _, err := PortableDefinition(bundle)
	if err != nil || got != digest {
		t.Fatal("alias/order changed definition", got, err)
	}
	fields := packagefmt.Object(packagefmt.Object(connection["authentication"])["fields"])
	packagefmt.Object(fields["api_key"])["key"] = "OTHER_KEY"
	got, _, err = PortableDefinition(bundle)
	if err != nil || got == digest {
		t.Fatal("authentication meaning not sealed", got, err)
	}
}

func TestConfigurationCaptureCompileCheckpointAndAuthorRestore(t *testing.T) {
	// A process variable with the same name must never enter a remote reference.
	t.Setenv("PRIMARY_KEY", "local-value-must-not-be-consumed")
	bundle, expected := configurationBundle(t)
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	state, err := c.ReadState("https://woobe.test", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	agentID, _ := NewID()
	modelID, _ := NewID()
	providerID, _ := NewID()
	captured := map[string]CapturedBinding{"agent": {ResourceID: agentID, Revision: 1, SourceKind: "draft"}, "model": {ResourceID: modelID, Revision: "revision"}}
	root, conflicts, err := c.ImportCapture(bundle, state, captured, map[string]string{"primary": providerID}, "support", "")
	if err != nil || len(conflicts) > 0 {
		t.Fatal(err, conflicts)
	}
	state.Requirements["secrets"] = []any{map[string]any{"ref": "unrelated-legacy"}}
	graph, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	compiled, bindings, err := graph.Compile(root.Key, state.Requirements, state.Credentials)
	if err != nil {
		t.Fatal(err)
	}
	defer compiled.Close()
	digest, _, err := PortableDefinition(compiled)
	if err != nil || digest != expected.Definition {
		t.Fatal("capture changed remote meaning", digest, expected.Definition, err)
	}
	if bindings["schema_version"] != "2.0" {
		t.Fatal(bindings)
	}
	if err = c.BootstrapTracking(*root, state, "production"); err != nil {
		t.Fatal(err)
	}
	record, err := graph.CreateRevision(*root, state, "Remote configuration", nil)
	if err != nil {
		t.Fatal(err)
	}
	if record.DefinitionScope != ConfigurationDefinitionScope {
		t.Fatal(record)
	}
	if err = ValidateRemoteRevision(*root, *record); err != nil {
		t.Fatal(err)
	}
	source, err := c.ReadAuthorObject(*root, record)
	if err != nil {
		t.Fatal(err)
	}
	tracking, err := c.ReadTracking(*root)
	if err != nil {
		t.Fatal(err)
	}
	if err = graph.validateAuthorExecution(*root, record, source, tracking); err != nil {
		t.Fatal(err)
	}
	count := len(c.Resources)
	if _, conflicts, err = c.ImportCapture(bundle, state, captured, map[string]string{"primary": providerID}, "support", ""); err != nil || len(conflicts) != 0 || len(c.Resources) != count {
		t.Fatal("repeat capture duplicated resources", conflicts, err)
	}
}

func TestLegacyCompileIgnoresUnrelatedRemoteDeclarations(t *testing.T) {
	_, graph := completeGraph(t)
	state := authorState()
	state.Requirements["configuration"] = map[string]any{"keys": []any{map[string]any{"key": "UNRELATED", "kind": "secret"}}}
	bundle, _, err := graph.Compile("support", state.Requirements, nil)
	if err != nil {
		t.Fatal("mixed registry changed legacy contract", err)
	}
	defer bundle.Close()
	if DefinitionScope(bundle.Graph.Manifest) != PortableDefinitionScope {
		t.Fatal("legacy closure upgraded implicitly")
	}
}
